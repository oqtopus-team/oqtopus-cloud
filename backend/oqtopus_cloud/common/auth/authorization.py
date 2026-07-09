"""Authorization: decide whether an *authenticated* caller may access the API.

This mirrors the account-status portion of the Lambda authorizer
(``lambda_auth/lambda_function.py::_validate_user_status``). Authentication
(token/credential validity) is handled upstream -- by the API Gateway authorizer
in ``aws`` mode, or by oauth2-proxy + the OIDC verification in ``oidc`` mode.
What remains, and what this module owns, is the app-level authorization gate:
the user must exist in the DB and be ``approved``.

MFA is intentionally NOT re-checked here: in the OIDC deployment MFA is enforced
by the identity provider (Keycloak), not by this service.
"""

import os

from sqlalchemy import select

from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import (
    AUTH_DB_READ_TIMEOUT_SECONDS,
    _create_session,
)


def _status_enforced() -> bool:
    return os.getenv("AUTH_ENFORCE_STATUS", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


def validate_user_status(user_id: str) -> bool:
    """Return True iff ``user_id`` maps to an ``approved`` user.

    Set ``AUTH_ENFORCE_STATUS=false`` to skip the check (e.g. for a demo where
    the IdP is the only gate and no user rows are provisioned yet).
    """
    if not _status_enforced():
        return True

    db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        user = db.execute(
            select(User).where(
                User.id == user_id,
                User.userstatus == UserStatus.approved,
            )
        ).scalar()
    finally:
        db.close()
    return user is not None
