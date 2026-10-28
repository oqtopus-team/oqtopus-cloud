"""First-login identity provisioning for the on-prem OIDC path (Phase 1).

On-prem there is no Cognito sign-up flow, so a brand-new LDAP user has no
``users`` row and would be rejected by the approved gate. When
``OIDC_AUTO_PROVISION=true`` the User API, *after* verifying the OIDC token and
*before* the approved check, creates the row in ``unapproved`` state so an admin
can approve it.

Phase 1 keeps the existing schema invariant ``users.id = email`` and stores the
IdP subject (Keycloak ``sub``) in ``users.cognito_id`` (NOT NULL UNIQUE) -- the
same column Cognito uses. The internal-UUID / ``user_identities`` migration is
Phase 2.

Invariants enforced here:

- Runs only on the OIDC browser path (never Q-API-Token or Admin auth), only
  after the token's signature/issuer/audience/expiry were verified.
- Never auto-approves (status = ``unapproved``).
- Never updates or merges an existing row: a ``sub`` whose email changed, or an
  email already used by a different ``sub``, is a conflict -> 403, no DB change.
- Idempotent via the PK (``id = email``) and the unique ``cognito_id``; a
  concurrent first login that loses the race is rolled back and re-resolved.
- Does not create a row when the email claim is missing.
- Audits creations and conflicts.
"""

import logging
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from oqtopus_cloud.common.auth.frontend import AuthorizationError
from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import _create_session

_audit = logging.getLogger("oqtopus_cloud.auth.provisioning")


def auto_provision_enabled() -> bool:
    """True when first-login provisioning is turned on (on-prem OIDC only)."""
    return os.getenv("OIDC_AUTO_PROVISION", "").strip().lower() in ("true", "1", "yes")


class IdentityConflictError(AuthorizationError):
    """A first-login provisioning conflict (-> 403); the existing row is left as-is."""


def provision_oidc_user(sub: str, claims: dict) -> None:
    """Create an ``unapproved`` row for a never-seen ``sub`` (first login).

    No-op when the ``sub`` already maps to a row. Raises
    :class:`IdentityConflictError` (403) on an email/sub conflict without
    touching the DB. Must be called only after the token is verified and only in
    auto-provision (OIDC browser) mode.
    """
    email = claims.get("email")
    if not email or not isinstance(email, str):
        # No stable identity to create a row from; leave the DB untouched. The
        # caller's approved gate then yields 403.
        _audit.warning("provision skipped: token has no usable email claim (sub=%s)", sub)
        return

    db = _create_session()
    try:
        row = db.execute(select(User).where(User.cognito_id == sub)).scalar()
        if row is not None:
            # sub already provisioned (approved or not). Never auto-update email:
            # a changed email is a conflict, handled out of band.
            if str(row.id) != email or row.email != email:
                _audit.warning(
                    "provision conflict: sub already maps to a different email "
                    "(sub=%s, token_email=%s, db_id=%s)",
                    sub,
                    email,
                    row.id,
                )
                raise IdentityConflictError(
                    "The identity's email does not match its existing record."
                )
            return
        # sub absent: refuse to take over an email already used by another sub.
        clash = db.execute(select(User).where(User.id == email)).scalar()
        if clash is not None:
            _audit.warning(
                "provision conflict: email already used by another identity "
                "(email=%s, existing_sub=%s, token_sub=%s)",
                email,
                clash.cognito_id,
                sub,
            )
            raise IdentityConflictError("This email is already registered.")
        try:
            db.add(
                User(
                    id=email,
                    email=email,
                    cognito_id=sub,
                    userstatus=UserStatus.unapproved,
                )
            )
            db.commit()
            _audit.info("provisioned unapproved user (sub=%s, email=%s)", sub, email)
        except IntegrityError:
            # A concurrent first login created the row first: roll back and
            # re-resolve. Accept it only if it matches this identity, else 403.
            db.rollback()
            row = db.execute(select(User).where(User.cognito_id == sub)).scalar()
            if row is None or str(row.id) != email or row.email != email:
                _audit.warning(
                    "provision conflict on concurrent create (sub=%s, email=%s)",
                    sub,
                    email,
                )
                raise IdentityConflictError(
                    "Could not provision the identity due to a conflict."
                )
    finally:
        db.close()
