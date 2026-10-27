"""OIDC Bearer-token verification for the OQTOPUS backend.

Thin adapter over the shared :mod:`oqtopus_auth` library. The backend resolves
OIDC settings from environment variables (``OIDC_ISSUER`` / ``OIDC_JWKS_URL`` /
``OIDC_AUDIENCE`` / ``OIDC_ALGORITHMS`` / ``OIDC_ALLOW_ANY_AUDIENCE`` /
``OIDC_CLIENT_ID`` / ``OIDC_CLIENT_ID_CLAIM`` / ``OIDC_TOKEN_USE``); this module
maps them onto an ``oqtopus_auth.OidcProviderConfig`` and delegates the actual
verification and scope handling to the library, so both the user- and
machine-identity paths share one audited implementation.

Token binding is fail-closed: a token must be bound to this app by ``aud``
(``OIDC_AUDIENCE``) or by the client-id claim (``OIDC_CLIENT_ID`` -- for issuers
whose access tokens carry no ``aud``, e.g. Cognito), or the operator must
explicitly opt out with ``OIDC_ALLOW_ANY_AUDIENCE=true``. Setting none is a
configuration error. ``OIDC_TOKEN_USE=access`` rejects id tokens where an access
token is expected.
"""

import os

from oqtopus_auth import (
    OidcError,
    OidcProviderConfig,
    extract_scopes,
    has_required_scope,
)
from oqtopus_auth import verify_bearer_token as _lib_verify_bearer_token
from pydantic import ValidationError

__all__ = [
    "OidcError",
    "extract_scopes",
    "has_required_scope",
    "verify_bearer_token",
]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("true", "1", "yes")


def _parse_client_id(raw: str | None) -> str | list[str] | None:
    """Parse ``OIDC_CLIENT_ID`` (single value, or comma-separated list)."""
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else parts


def _config_from_env() -> OidcProviderConfig:
    issuer = os.getenv("OIDC_ISSUER")
    if not issuer:
        raise OidcError("OIDC_ISSUER is not configured")
    audience = os.getenv("OIDC_AUDIENCE") or None
    allow_any_audience = _env_flag("OIDC_ALLOW_ANY_AUDIENCE")
    # Bind by client_id when the issuer's access tokens carry no `aud` (e.g.
    # Cognito access tokens without a resource binding). `token_use` lets the
    # access token be distinguished from an id token.
    client_id = _parse_client_id(os.getenv("OIDC_CLIENT_ID"))
    client_id_claim = os.getenv("OIDC_CLIENT_ID_CLAIM", "client_id")
    token_use = os.getenv("OIDC_TOKEN_USE") or None
    # Fail-closed: never skip binding implicitly. Require a binding (audience or
    # client_id), or an explicit, deliberate opt-out.
    if audience is None and client_id is None and not allow_any_audience:
        raise OidcError(
            "no token binding configured; set OIDC_AUDIENCE, or OIDC_CLIENT_ID "
            "(for issuers whose access tokens carry no aud, e.g. Cognito), or "
            "explicitly opt out with OIDC_ALLOW_ANY_AUDIENCE=true"
        )
    algorithms = [
        a.strip() for a in os.getenv("OIDC_ALGORITHMS", "RS256").split(",") if a.strip()
    ]
    try:
        return OidcProviderConfig(
            issuer=issuer,
            jwks_url=os.getenv("OIDC_JWKS_URL") or None,
            audience=audience,
            allow_any_audience=allow_any_audience,
            client_id=client_id,
            client_id_claim=client_id_claim,
            token_use=token_use,
            algorithms=algorithms,
        )
    except ValidationError as e:
        raise OidcError(f"invalid OIDC configuration: {e}") from e


def verify_bearer_token(token: str) -> dict:
    """Verify an OIDC JWT against the env-configured issuer and return its claims.

    Raises :class:`oqtopus_auth.OidcError` on any failure.
    """
    return _lib_verify_bearer_token(token, _config_from_env())
