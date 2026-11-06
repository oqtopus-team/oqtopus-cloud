"""Admin-API identity resolution (flexible ``AUTH_MODE``).

The Admin API authenticates *operators*, not end users, so its authorization
model differs from the User API:

- there is no DB ``users.status`` approval gate -- being an admin *is* the
  authorization, and
- the AWS deployment keeps the API Gateway **Cognito authorizer** (unlike the
  User API's in-app "case A"), so in ``aws`` mode this module only reads the
  identity the authorizer already verified and injected.

Dispatch on ``AUTH_MODE`` (shared with the User API via :func:`auth_mode`):

- ``local`` : hardcoded developer identity (the existing ``ENV=local`` bypass).
- ``aws``   : read ``cognito:username`` from the Cognito-authorizer claims.
              Unchanged prod behavior.
- ``oidc``  : verify a Bearer JWT in-app (e.g. Keycloak behind oauth2-proxy) and
              require a configured admin role/group claim. "Being an admin" =
              holding that role; without it the caller is authenticated but not
              permitted (403).
"""

import os
from typing import Any

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from fastapi import Request

from oqtopus_cloud.common.auth.frontend import (
    AuthError,
    AuthorizationError,
    Identity,
    auth_mode,
)
from oqtopus_cloud.common.auth.oidc import OidcError, verify_bearer_token


def _local_admin_identity() -> Identity:
    # Preserves the previous ENV=local hardcoded developer identity.
    return Identity(
        user_id="admin",
        user_pool_id="ap-northeast-1_XXXXXXXXX",
        region="ap-northeast-1",
        auth_method="local",
    )


def _aws_admin_identity(request: Request) -> Identity:
    # Unchanged prod behavior: the API Gateway Cognito authorizer verified the
    # admin's token and injected its claims; read the username from there. A
    # missing event/authorizer raises KeyError, which the middleware maps to a
    # 500 (as before), not a 401.
    claims = (
        APIGatewayProxyEvent(request.scope["aws.event"])
        .request_context.authorizer.claims
    )
    user_id = claims["cognito:username"]
    user_pool_id = os.getenv("CLIENT_COGNITO_USER_POOL_ID")
    region = user_pool_id.split("_")[0] if user_pool_id else None
    return Identity(
        user_id=user_id,
        user_pool_id=user_pool_id,
        region=region,
        auth_method="aws",
    )


def _extract_roles(claims: dict, claim_path: str) -> list[str]:
    """Read a (possibly nested) roles/groups claim as a list of strings.

    ``claim_path`` is a dot-path so one setting spans IdPs: ``realm_access.roles``
    (Keycloak realm roles) or ``cognito:groups`` (a single top-level claim).
    A missing path or an unexpected shape yields no roles, which fails closed at
    the caller.
    """
    node: Any = claims
    for segment in claim_path.split("."):
        if not isinstance(node, dict) or segment not in node:
            return []
        node = node[segment]
    if isinstance(node, str):
        return [node]
    if isinstance(node, (list, tuple)):
        return [r for r in node if isinstance(r, str)]
    return []


def _oidc_admin_identity(request: Request) -> Identity:
    # Authentication: the verified OIDC token arrives as a Bearer (injected by
    # oauth2-proxy on-prem).
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise AuthError("Missing Authorization header")
    token = auth_header.removeprefix("Bearer ").removeprefix("bearer ").strip()
    if not token:
        raise AuthError("Empty Bearer token")

    try:
        claims = verify_bearer_token(token)
    except OidcError as e:
        raise AuthError(str(e))

    # Who is the operator.
    principal_claim = os.getenv("ADMIN_PRINCIPAL_CLAIM", "preferred_username")
    user_id = claims.get(principal_claim)
    if not user_id or not isinstance(user_id, str):
        raise AuthError(f"Token is missing the '{principal_claim}' claim")

    # Authorization: the operator must hold the configured admin role/group.
    # The required role MUST be set in oidc mode -- leaving it unset is a
    # fail-closed *configuration* error (surfaced as a 500 so a misdeploy is
    # obvious), never an implicit "any authenticated user is an admin".
    required_role = os.getenv("ADMIN_REQUIRED_ROLE", "").strip()
    if not required_role:
        raise RuntimeError(
            "ADMIN_REQUIRED_ROLE is not configured; refusing to authorize any "
            "admin in AUTH_MODE=oidc"
        )
    roles_claim = os.getenv("ADMIN_ROLES_CLAIM", "realm_access.roles")
    if required_role not in _extract_roles(claims, roles_claim):
        # Authenticated but not permitted -> 403; re-authenticating won't help.
        raise AuthorizationError(f"Admin role '{required_role}' is required")

    return Identity(user_id=user_id, email=claims.get("email"), auth_method="oidc")


def resolve_admin_identity(request: Request) -> Identity:
    """Resolve the admin caller identity for the active :func:`auth_mode`."""
    mode = auth_mode()
    if mode == "local":
        return _local_admin_identity()
    if mode == "aws":
        return _aws_admin_identity(request)
    if mode == "oidc":
        return _oidc_admin_identity(request)
    raise AuthError(f"Unknown AUTH_MODE: {mode!r}")
