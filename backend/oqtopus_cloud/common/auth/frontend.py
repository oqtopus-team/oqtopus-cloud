"""Resolve the caller's identity from the incoming request.

The dispatch on ``AUTH_MODE`` is the single seam that decouples the FastAPI apps
from any specific identity provider. Each strategy produces an :class:`Identity`
whose ``user_id`` matches the DB ``users.id`` / ``jobs.owner`` key (an email in
practice), so everything downstream is unchanged regardless of how the caller
authenticated.
"""

import os
from dataclasses import dataclass
from typing import Optional

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from fastapi import Request

from oqtopus_cloud.common.auth.authorization import (
    resolve_user_by_cognito_id,
    validate_user_status,
)
from oqtopus_cloud.common.auth.oidc import OidcError, verify_bearer_token


class AuthError(Exception):
    """Authentication failure: the caller could not be authenticated (-> 401).

    ``challenge`` is the ``WWW-Authenticate`` value a 401 should advertise.
    It defaults to ``"Bearer"`` (the OIDC path), but the Q-API-Token path sets
    it to ``None`` so a CLI token failure is not told to retry as a Bearer.
    """

    def __init__(self, message: str = "", *, challenge: Optional[str] = "Bearer"):
        super().__init__(message)
        self.challenge = challenge


class AuthorizationError(AuthError):
    """Authorization failure: authenticated but not permitted (-> 403).

    A subclass of :class:`AuthError` so callers that catch the latter keep
    working; middlewares that distinguish 401 vs 403 check this type first.
    """


@dataclass
class Identity:
    """The resolved caller identity handed to the request handlers."""

    user_id: str
    email: Optional[str] = None
    user_pool_id: Optional[str] = None
    region: Optional[str] = None
    # How the caller authenticated: "local" | "aws" | "oidc" | "api_token".
    # Lets handlers gate sensitive operations (e.g. forbid an API-token caller
    # from minting a fresh API token without interactive re-authentication).
    auth_method: Optional[str] = None


def auth_mode() -> str:
    """Return the active auth mode.

    Explicit ``AUTH_MODE`` wins; otherwise fall back to the historical behavior
    (``local`` when ``ENV=local``, else ``aws``) so nothing changes for existing
    deployments and tests.
    """
    mode = os.getenv("AUTH_MODE")
    if mode:
        return mode.strip().lower()
    return "local" if os.getenv("ENV") == "local" else "aws"


def _local_identity() -> Identity:
    # Preserves the previous ENV=local hardcoded developer identity.
    return Identity(
        user_id="admin-email",
        email="admin-email",
        user_pool_id="ap-northeast-1_XXXXXXXXX",
        region="ap-northeast-1",
        auth_method="local",
    )


def _aws_identity(request: Request) -> Identity:
    # Unchanged prod behavior: read the id the Lambda authorizer injected.
    # A missing event/authorizer raises KeyError, which the middleware maps to
    # a 500 (as before) rather than a 401.
    user_id = APIGatewayProxyEvent(
        request.scope["aws.event"]
    ).request_context.authorizer["user_id"]
    user_pool_id = os.getenv("CLIENT_COGNITO_USER_POOL_ID")
    region = user_pool_id.split("_")[0] if user_pool_id else None
    return Identity(
        user_id=user_id,
        user_pool_id=user_pool_id,
        region=region,
        auth_method="aws",
    )


def _oidc_identity(request: Request) -> Identity:
    # Authentication: the verified OIDC token arrives as a Bearer (injected by
    # oauth2-proxy on-prem, or sent by the SPA/Amplify on AWS).
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

    # How to map verified claims -> internal user identity:
    #   "direct"      (default): a claim's value *is* the users.id (Keycloak
    #                 access token with email; on-prem).
    #   "cognito_sub"          : resolve users.id via users.cognito_id == sub.
    #                 Required for Cognito access tokens, whose only stable id is
    #                 `sub` (the `username` claim is a UUID) and which carry no
    #                 email. Selected explicitly -- never inferred from `issuer`.
    resolver = os.getenv("OIDC_IDENTITY_RESOLVER", "direct").strip().lower()
    if resolver == "cognito_sub":
        return _identity_via_cognito_sub(claims)
    if resolver == "direct":
        return _identity_direct(claims)
    # A typo (e.g. "cognito_sbu") must fail closed, not silently become "direct".
    raise AuthError(f"Unsupported OIDC_IDENTITY_RESOLVER: {resolver!r}")


def _identity_direct(claims: dict) -> Identity:
    username_claim = os.getenv("OIDC_USERNAME_CLAIM", "email")
    user_id = claims.get(username_claim)
    if not user_id or not isinstance(user_id, str):
        raise AuthError(f"Token is missing the '{username_claim}' claim")

    # Authorization: the account must exist and be approved (the piece the
    # Lambda authorizer used to enforce upstream). Authenticated-but-unapproved
    # is a 403, not a 401 -- re-authenticating would not help.
    if not validate_user_status(user_id=user_id):
        raise AuthorizationError(f"User '{user_id}' is not approved")

    return Identity(user_id=user_id, email=claims.get("email"), auth_method="oidc")


def _identity_via_cognito_sub(claims: dict) -> Identity:
    principal_claim = os.getenv("OIDC_PRINCIPAL_CLAIM", "sub")
    sub = claims.get(principal_claim)
    # A missing/non-string principal is an authentication failure (401).
    if not sub or not isinstance(sub, str):
        raise AuthError(f"Token is missing the '{principal_claim}' claim")

    # Resolve users.id/email via users.cognito_id (+ approved gate). A DB error
    # propagates (500); None means unknown or unapproved -> 403. The email is
    # taken from the DB, since Cognito access tokens carry no email claim.
    resolved = resolve_user_by_cognito_id(sub)
    if resolved is None:
        raise AuthorizationError(f"No approved user for {principal_claim}={sub!r}")

    user_id, email = resolved
    return Identity(user_id=user_id, email=email, auth_method="oidc")


def resolve_identity(request: Request) -> Identity:
    """Resolve the caller identity for the active :func:`auth_mode`."""
    mode = auth_mode()
    if mode == "local":
        return _local_identity()
    if mode == "aws":
        return _aws_identity(request)
    if mode == "oidc":
        # "oidc" = verify the token in-app (not an on-prem-only mode): used both
        # on AWS (Cognito, case A -- no API Gateway authorizer) and on-prem
        # (Keycloak). The User API serves two caller kinds that AWS's Lambda
        # authorizer used to unify: browsers (OIDC Bearer) and CLI clients
        # (a DB-backed Q-API-Token). Dispatch on the token header. Deferred
        # import avoids a frontend<->client module cycle.
        from oqtopus_cloud.common.auth.client import (  # noqa: PLC0415
            API_TOKEN_HEADER,
            resolve_api_token_identity,
        )

        if request.headers.get(API_TOKEN_HEADER):
            return resolve_api_token_identity(request)
        return _oidc_identity(request)
    raise AuthError(f"Unknown AUTH_MODE: {mode!r}")
