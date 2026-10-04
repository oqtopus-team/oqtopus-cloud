"""Resolve a CLI client's identity from a DB-backed ``Q-API-Token`` (on-prem).

Programmatic clients (``oqtopus-client`` / ``quri-parts-oqtopus``) authenticate
to the User API with a static ``Q-API-Token: <id>.<secret>`` header rather than
OIDC -- so this path never talks to an IdP. In AWS the token is verified by the
API Gateway Lambda authorizer; on-prem the same check runs in-app here.

Credential verification itself lives in :mod:`common.auth.api_token` (shared
with the Lambda authorizer so the two cannot drift). This module adds only the
on-prem concerns: reading the header, mapping to an :class:`Identity`, the
domain authorization (approved status), and the 401-vs-403 contract. It is
IdP-agnostic: no Cognito ``ListUsers`` / MFA-enabled / ``cognito_id`` lookup.
The resolved ``user_id`` is ``users.id`` (an email in practice), matching every
other auth path so downstream handlers are unchanged.
"""

from __future__ import annotations

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
        AuthorizationError: If the token's user is not approved (-> 403).

    """
    raw = request.headers.get(API_TOKEN_HEADER)
    # Reject a missing/malformed header before opening a DB session. A
    # Q-API-Token failure is not a Bearer/OIDC failure: do not advertise a
    # Bearer challenge, or the CLI is pointed at the wrong auth scheme.
    try:
        token_id, secret = parse_api_token(raw)
    except ApiTokenError as e:
        raise AuthError(str(e), challenge=None) from e

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

        # Read what we need *before* any commit: rehash below commits, which
        # (expire_on_commit) would otherwise make reading user.id re-SELECT (and
        # raise if the row was concurrently deleted). token_id (from the parser)
        # already equals user.api_token_id, since that's what we looked up by.
        user_id = str(user.id)
        current_hash = user.api_token_hash

        # Fully accepted -> opportunistic hash upgrade (never for a rejected req).
        rehash_api_token_if_needed(db, token_id, current_hash, secret)
        return Identity(user_id=user_id, auth_method="api_token")
    finally:
        db.close()
