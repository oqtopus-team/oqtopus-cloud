"""Resolve a CLI client's identity from a DB-backed ``Q-API-Token``.

Programmatic clients (``oqtopus-client`` / ``quri-parts-oqtopus``) authenticate
to the User API with a static ``Q-API-Token: <id>.<secret>`` header rather than
OIDC -- so this path never talks to an IdP for *authentication*. Credential
verification itself lives in :mod:`common.auth.api_token` (shared with the
Lambda authorizer so the two cannot drift).

Authorization depends on ``USER_AUTH_POLICY``:

- ``oidc`` (on-prem / generic OIDC): the account must be ``approved``. No
  Cognito dependency -- no ``ListUsers`` / MFA / ``cognito_id`` lookup.
- ``cognito`` (AWS, case-A in-app): in addition to ``approved``, the same
  conditions the Lambda authorizer enforced -- MFA ``enabled``, a non-null
  ``cognito_id``, and the user still present in the Cognito User Pool
  (``ListUsers``). These run via :mod:`common.auth.cognito_policy`, shared with
  the Lambda authorizer. The Cognito network call is made only *after* the DB
  session is closed, so no RDS Proxy connection is held across it.

The resolved ``user_id`` is ``users.id`` (an email in practice), matching every
other auth path so downstream handlers are unchanged.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from oqtopus_cloud.common.auth.api_token import (
    ApiTokenError,
    parse_api_token,
    rehash_api_token_if_needed,
    verify_api_token,
)
from oqtopus_cloud.common.auth.frontend import (
    AuthError,
    AuthorizationError,
    Identity,
    user_auth_policy,
)
from oqtopus_cloud.common.models.user import UserStatus
from oqtopus_cloud.common.session import (
    AUTH_DB_READ_TIMEOUT_SECONDS,
    _create_session,
)

if TYPE_CHECKING:
    from fastapi import Request

API_TOKEN_HEADER = "q-api-token"


def resolve_api_token_identity(request: Request) -> Identity:
    """Resolve the caller from the ``Q-API-Token`` header (DB-backed).

    Returns:
        An ``Identity`` whose ``user_id`` is the token owner's ``users.id``.

    Raises:
        AuthError: If the token is missing, malformed, unknown, has a bad
            secret, or is expired (-> 401).
        AuthorizationError: If the token's user is not approved, or (Cognito
            policy) lacks MFA / has no cognito_id / no longer exists in the
            Cognito User Pool (-> 403).
        CognitoLookupError: (Cognito policy) if the Cognito directory cannot be
            queried or is ambiguous -- propagates as a 500/503 (fail-closed).
    """
    raw = request.headers.get(API_TOKEN_HEADER)
    # Reject a missing/malformed header before opening a DB session. A
    # Q-API-Token failure is not a Bearer/OIDC failure: do not advertise a
    # Bearer challenge, or the CLI is pointed at the wrong auth scheme.
    try:
        token_id, secret = parse_api_token(raw)
    except ApiTokenError as e:
        raise AuthError(str(e), challenge=None) from e

    policy = user_auth_policy()

    # Phase 1: verify the token and read everything we need, then CLOSE the DB
    # session -- the Cognito call below must not pin an RDS Proxy connection.
    db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        try:
            user = verify_api_token(db, token_id, secret)
        except ApiTokenError as e:
            raise AuthError(str(e), challenge=None) from e

        # Authenticated via a valid token, but the account must be approved.
        # Unapproved is a 403 (re-issuing a token would not help), not a 401.
        if user.userstatus != UserStatus.approved:
            raise AuthorizationError(f"User '{user.id}' is not approved")

        # Read what we need *before* closing. token_id (from the parser) already
        # equals user.api_token_id, since that's what we looked up by.
        user_id = str(user.id)
        current_hash = user.api_token_hash
        # Cognito-policy inputs are read only when that policy is active, so the
        # on-prem path never depends on these columns.
        mfa_status = user.mfa_status if policy == "cognito" else None
        cognito_id = user.cognito_id if policy == "cognito" else None
    finally:
        db.close()

    # Phase 2 (AWS Cognito policy only): MFA enabled + cognito_id + the user
    # still exists in the Cognito User Pool. No DB connection is held here.
    if policy == "cognito":
        from oqtopus_cloud.common.auth.cognito_policy import (  # noqa: PLC0415
            CognitoIdMissing,
            CognitoUserNotFound,
            MfaNotEnabled,
            enforce_api_token_cognito_policy,
        )

        user_pool_id = os.environ["CLIENT_COGNITO_USER_POOL_ID"]
        try:
            enforce_api_token_cognito_policy(
                mfa_status, cognito_id, user_pool_id=user_pool_id
            )
        except (MfaNotEnabled, CognitoIdMissing, CognitoUserNotFound) as e:
            # Authenticated but not permitted -> 403.
            raise AuthorizationError(str(e)) from e
        # CognitoLookupError (Cognito unreachable / ambiguous) is NOT caught:
        # it propagates and is surfaced as a server error (500), never a silent
        # accept and never a 403 -- fail-closed.

    # Phase 3: fully accepted -> opportunistic hash upgrade in a fresh, short
    # session (never for a rejected request; no connection held during Cognito).
    rehash_db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        rehash_api_token_if_needed(rehash_db, token_id, current_hash, secret)
    finally:
        rehash_db.close()
    return Identity(user_id=user_id, auth_method="api_token")
