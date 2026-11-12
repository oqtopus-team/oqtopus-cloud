"""AWS Cognito authorization checks, shared by both auth entry points.

The AWS deployment's authorization policy (MFA must be enabled, and for a
Q-API-Token the user must still exist in the Cognito User Pool) is enforced in
two places: the API Gateway Lambda authorizer (``lambda_auth``) and, under
``AUTH_MODE=oidc`` case-A, the in-app User-API resolver (``common.auth.client``
/ ``frontend``). Keeping the checks here, in one module both call, is what stops
the two from drifting again -- the regression this module exists to prevent.

These helpers raise their own neutral exceptions; each caller maps them to its
own result (the Lambda authorizer denies; the in-app path maps to 401/403/500).
``CognitoUserNotFound`` is an authorization failure (the user is gone -> 403),
while ``CognitoLookupError`` is an infrastructure failure (Cognito unreachable,
or an ambiguous/duplicate result -> 500/503). Both are fail-closed: the token is
never accepted when the Cognito side cannot be confirmed.

IMPORTANT: :func:`require_cognito_user_exists` performs a network call. Callers
must NOT hold a database connection across it (close the DB session first), so
an RDS Proxy connection is not pinned during the Cognito round-trip.
"""

from __future__ import annotations

from typing import Any, Optional

import boto3
from botocore.config import Config

from oqtopus_cloud.common.models.user import MFAStatus

# Short, explicit timeouts so a stalled Cognito call fails fast instead of
# consuming the whole request/Lambda budget. Mirrors lambda_auth's config:
# connect 2s, read 3s, total_max_attempts 2 (one initial + one retry).
_BOTO_TIMEOUT_CONFIG = Config(
    connect_timeout=2,
    read_timeout=3,
    retries={"total_max_attempts": 2, "mode": "standard"},
)


class CognitoPolicyError(Exception):
    """Base class for an AWS Cognito authorization-policy failure."""


class MfaNotEnabled(CognitoPolicyError):
    """The user's DB ``mfa_status`` is not ``enabled`` (-> 403)."""


class CognitoIdMissing(CognitoPolicyError):
    """The user has no ``cognito_id`` to look up (-> 403)."""


class CognitoUserNotFound(CognitoPolicyError):
    """No Cognito user matches the ``sub`` -- account deleted/disabled (-> 403)."""


class CognitoLookupError(CognitoPolicyError):
    """Cognito could not be queried, or returned an ambiguous result (-> 500/503).

    Distinct from :class:`CognitoUserNotFound`: this is an infrastructure/data
    integrity problem, not a decision that the caller lacks permission. Still
    fail-closed -- the token must not be accepted.
    """


def require_mfa_enabled(mfa_status: Any) -> None:
    """Raise :class:`MfaNotEnabled` unless ``mfa_status`` is ``enabled``."""
    if mfa_status != MFAStatus.enabled:
        raise MfaNotEnabled("MFA is not enabled for this user")


def _cognito_client(user_pool_id: str) -> Any:
    # Region is encoded in the pool id ("<region>_XXXX"), matching
    # session.get_cognito_client and _aws_identity.
    region = user_pool_id.split("_")[0] if user_pool_id else None
    return boto3.client("cognito-idp", region_name=region, config=_BOTO_TIMEOUT_CONFIG)


def require_cognito_user_exists(
    cognito_id: Optional[str],
    *,
    user_pool_id: str,
    client: Any = None,
) -> dict:
    """Confirm exactly one Cognito user has ``sub == cognito_id``; return it.

    Fail-closed:
        - missing ``cognito_id`` -> :class:`CognitoIdMissing` (403)
        - zero matches -> :class:`CognitoUserNotFound` (403, account gone)
        - a Cognito error, or more than one match -> :class:`CognitoLookupError`
        (500/503; never silently accepted)

    Returns the single matched Cognito user record (so a caller that needs the
    Cognito ``Username`` can read it). Must be called with NO database
    connection held (it performs a network call).
    """
    if not cognito_id:
        raise CognitoIdMissing("Cognito id is not found")
    if client is None:
        client = _cognito_client(user_pool_id)
    try:
        response = client.list_users(
            UserPoolId=user_pool_id, Filter=f'sub = "{cognito_id}"'
        )
    except Exception as e:  # noqa: BLE001 -- any Cognito/SDK failure is fail-closed
        raise CognitoLookupError(f"Failed to list users from Cognito: {e}") from e

    users = response.get("Users", [])
    if len(users) == 0:
        raise CognitoUserNotFound("Cognito user is not found")
    if len(users) > 1:
        # An ambiguous directory is a data-integrity problem, not a per-user
        # authorization decision -> treat as a lookup failure (500), not a 403.
        raise CognitoLookupError("Cognito user is duplicated")
    return users[0]


def enforce_api_token_cognito_policy(
    mfa_status: Any,
    cognito_id: Optional[str],
    *,
    user_pool_id: str,
    client: Any = None,
) -> None:
    """Apply the full AWS Cognito policy for a Q-API-Token caller.

    MFA enabled, a non-null ``cognito_id``, and the user still present in the
    Cognito User Pool. Call only after the DB session has been closed.
    """
    require_mfa_enabled(mfa_status)
    require_cognito_user_exists(cognito_id, user_pool_id=user_pool_id, client=client)
