"""Resolve a CLI client's identity from a DB-backed ``Q-API-Token`` (on-prem).

Programmatic clients (``oqtopus-client`` / ``quri-parts-oqtopus``) authenticate
to the User API with a static ``Q-API-Token: <id>.<secret>`` header rather than
OIDC -- so this path never talks to an IdP. In AWS the token is verified by the
API Gateway Lambda authorizer; on-prem the same check runs in-app here.

Unlike the Lambda path this is IdP-agnostic: it drops the Cognito ``ListUsers``
existence lookup and the MFA-enabled requirement, verifying only the hashed
secret, the expiry, and the user's approved status in the DB. The resolved
``user_id`` is ``users.id`` (an email in practice), matching every other auth
path so downstream handlers are unchanged.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from sqlalchemy import select, update

from oqtopus_cloud.common.auth.frontend import (
    AuthError,
    AuthorizationError,
    Identity,
)
from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import (
    AUTH_DB_READ_TIMEOUT_SECONDS,
    _create_session,
)

if TYPE_CHECKING:
    from fastapi import Request

API_TOKEN_HEADER = "q-api-token"

_utc = ZoneInfo("UTC")
_ph = PasswordHasher()


def resolve_api_token_identity(request: Request) -> Identity:
    """Resolve the caller from the ``Q-API-Token`` header (DB-backed).

    Returns:
        An ``Identity`` whose ``user_id`` is the token owner's ``users.id``.

    Raises:
        AuthError: If the token is missing, malformed, unknown, has a bad
            secret, or is expired (-> 401).
        AuthorizationError: If the token's user is not approved (-> 403).

    """
    raw = request.headers.get(API_TOKEN_HEADER)
    if not raw:
        # A Q-API-Token failure is not a Bearer/OIDC failure: do not advertise a
        # Bearer challenge, or the CLI is pointed at the wrong auth scheme.
        raise AuthError("Missing Q-API-Token header", challenge=None)
    try:
        token_id, secret = raw.split(".")
    except ValueError:
        raise AuthError("Malformed Q-API-Token", challenge=None)

    db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        row = db.execute(
            select(
                User.id,
                User.api_token_hash,
                User.api_token_expiration,
                User.userstatus,
            ).where(User.api_token_id == token_id)
        ).first()
        if row is None or row.api_token_hash is None:
            raise AuthError("Invalid API token", challenge=None)
        user_id, token_hash, expiration, userstatus = row

        try:
            _ph.verify(token_hash, secret)
        except VerifyMismatchError:
            raise AuthError("Invalid API token", challenge=None)
        except (VerificationError, InvalidHash):
            raise AuthError("API token verification error", challenge=None)

        if expiration is None or expiration.astimezone(_utc) < datetime.now(_utc):
            raise AuthError("API token is expired", challenge=None)

        # Authenticated via a valid token, but the account must be approved.
        # Unapproved is a 403 (re-issuing a token would not help), not a 401.
        if userstatus != UserStatus.approved:
            raise AuthorizationError(f"User '{user_id}' is not approved")

        # Only a fully-accepted request mutates the DB. Rehash after all checks,
        # and guard on the hash we verified so a concurrent rotation (or token
        # deletion) is not clobbered by this opportunistic upgrade.
        if _ph.check_needs_rehash(token_hash):
            db.execute(
                update(User)
                .where(
                    User.api_token_id == token_id,
                    User.api_token_hash == token_hash,
                )
                .values(api_token_hash=_ph.hash(secret))
            )
            db.commit()

        return Identity(user_id=str(user_id), auth_method="api_token")
    finally:
        db.close()
