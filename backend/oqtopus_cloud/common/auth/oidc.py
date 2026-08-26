"""OIDC Bearer-token verification for the OQTOPUS backend.

Thin adapter over the shared :mod:`oqtopus_auth` library. The backend resolves
OIDC settings from environment variables (``OIDC_ISSUER`` / ``OIDC_JWKS_URL`` /
``OIDC_AUDIENCE`` / ``OIDC_ALGORITHMS`` / ``OIDC_ALLOW_ANY_AUDIENCE``); this
module maps them onto an ``oqtopus_auth.OidcProviderConfig`` and delegates the
actual verification and scope handling to the library, so both the user- and
machine-identity paths share one audited implementation.

Audience verification is fail-closed: ``OIDC_AUDIENCE`` must be set, or the
operator must explicitly opt out with ``OIDC_ALLOW_ANY_AUDIENCE=true`` (which
disables the ``aud`` check and allows tokens minted for other resources of the
same issuer). Setting neither is a configuration error.
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


def _config_from_env() -> OidcProviderConfig:
    issuer = os.getenv("OIDC_ISSUER")
    if not issuer:
        raise OidcError("OIDC_ISSUER is not configured")
    audience = os.getenv("OIDC_AUDIENCE") or None
    allow_any_audience = _env_flag("OIDC_ALLOW_ANY_AUDIENCE")
    # Fail-closed: never skip the aud check implicitly. Require an audience, or
    # an explicit, deliberate opt-out.
    if audience is None and not allow_any_audience:
        raise OidcError(
            "OIDC_AUDIENCE is not set; set it, or explicitly opt out of audience "
            "verification with OIDC_ALLOW_ANY_AUDIENCE=true"
        )
    algorithms = [
        a.strip()
        for a in os.getenv("OIDC_ALGORITHMS", "RS256").split(",")
        if a.strip()
    ]
    try:
        return OidcProviderConfig(
            issuer=issuer,
            jwks_url=os.getenv("OIDC_JWKS_URL") or None,
            audience=audience,
            allow_any_audience=allow_any_audience,
            algorithms=algorithms,
        )
    except ValidationError as e:
        raise OidcError(f"invalid OIDC configuration: {e}") from e


def verify_bearer_token(token: str) -> dict:
    """Verify an OIDC JWT against the env-configured issuer and return its claims.

    Raises :class:`oqtopus_auth.OidcError` on any failure.
    """
    return _lib_verify_bearer_token(token, _config_from_env())
