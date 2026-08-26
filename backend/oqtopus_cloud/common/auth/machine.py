"""Resolve a *machine* (M2M) caller identity for the Provider API.

The Provider API is called by machine clients (e.g. ``oqtopus-engine``), not by
human users. Historically the only gate was an API Gateway API key, so there was
no per-caller identity at all. This module adds a pluggable resolver -- mirroring
the user-facing :mod:`oqtopus_cloud.common.auth.identity` -- selected by the same
``AUTH_MODE`` environment variable:

- ``aws``   : the API Gateway validated the API key upstream; there is no
              per-caller identity. Preserves the existing production behavior.
- ``oidc``  : verify an OAuth2 *client-credentials* access token (JWKS) and
              require a configurable scope (``PROVIDER_REQUIRED_SCOPE``,
              default ``provider.write``). The principal is the client id.
- ``local`` : bypass (the existing ``ENV=local`` developer path).

Authorization here is intentionally coarse: any client presenting a valid token
with the required scope may act. Per-device scoping is out of scope.
"""

import os
from dataclasses import dataclass, field

from fastapi import Request

from oqtopus_cloud.common.auth.identity import AuthError, auth_mode
from oqtopus_cloud.common.auth.oidc import (
    OidcError,
    extract_scopes,
    has_required_scope,
    verify_bearer_token,
)

DEFAULT_REQUIRED_SCOPE = "provider.write"


@dataclass
class MachineIdentity:
    """The resolved identity of a machine (M2M) caller."""

    client_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)


def required_scope() -> str:
    """Return the scope a caller must present in ``oidc`` mode."""
    return os.getenv("PROVIDER_REQUIRED_SCOPE", DEFAULT_REQUIRED_SCOPE)


def _oidc_machine_identity(request: Request) -> MachineIdentity:
    # Authentication: the client presents a client-credentials access token.
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

    # Authorization: coarse scope gate (no user-status / DB check for M2M).
    scope = required_scope()
    if scope and not has_required_scope(claims, scope):
        raise AuthError(f"Token is missing required scope '{scope}'")

    # The principal of a client-credentials token is the client, not a user:
    # `azp`/`client_id` name it; fall back to `sub` (the service account).
    client_id = (
        claims.get("azp")
        or claims.get("client_id")
        or claims.get("sub")
        or "unknown"
    )
    return MachineIdentity(
        client_id=str(client_id),
        scopes=frozenset(extract_scopes(claims)),
    )


def resolve_machine_identity(request: Request) -> MachineIdentity:
    """Resolve the machine caller identity for the active :func:`auth_mode`."""
    mode = auth_mode()
    if mode == "local":
        return MachineIdentity(client_id="local")
    if mode == "aws":
        # The API Gateway API key was validated at the edge; there is no
        # per-caller identity to read. A missing aws.event is not expected here
        # (unlike the user API, provider routers don't need the authorizer
        # context), so we simply return a constant principal.
        return MachineIdentity(client_id="apigateway-api-key")
    if mode == "oidc":
        return _oidc_machine_identity(request)
    raise AuthError(f"Unknown AUTH_MODE: {mode!r}")
