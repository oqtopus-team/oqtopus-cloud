"""Generic OIDC Bearer-token verification.

This generalizes the Cognito-specific JWT verification that lived in the Lambda
authorizer (``lambda_auth/lambda_function.py::_verify_id_token``) to any OIDC
issuer -- Cognito, Keycloak, or anything else that exposes a JWKS endpoint.

Configuration (environment variables):
- ``OIDC_ISSUER``        (required) expected ``iss`` claim; also the base for
                          JWKS/discovery when the explicit URLs are not set.
- ``OIDC_JWKS_URL``      (optional) explicit JWKS endpoint. Useful when the
                          issuer that appears in the token (browser-facing host,
                          e.g. ``http://localhost:8080/...``) differs from the
                          host reachable from this service (``http://keycloak:8080/...``).
- ``OIDC_AUDIENCE``      (optional) expected ``aud``; when set, audience is
                          verified, otherwise the ``aud`` check is skipped.
- ``OIDC_ALGORITHMS``    (optional) comma-separated allow-list, default ``RS256``.
"""

import json
import os
import urllib.request
from functools import lru_cache

import jwt

# Match the authorizer's JWKS fetch timeout so a stalled IdP fails fast.
_JWKS_HTTP_TIMEOUT_SECONDS = 5
_DISCOVERY_HTTP_TIMEOUT_SECONDS = 5


class OidcError(Exception):
    """Raised when a Bearer token cannot be verified."""


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> "jwt.PyJWKClient":
    # PyJWKClient caches signing keys internally; lru_cache keeps one client per
    # URL so keys are not re-fetched on every request.
    return jwt.PyJWKClient(jwks_url, timeout=_JWKS_HTTP_TIMEOUT_SECONDS)


@lru_cache(maxsize=8)
def _discover_jwks_url(issuer: str) -> str:
    """Resolve the JWKS URL from the issuer's OIDC discovery document."""
    discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(
            discovery_url, timeout=_DISCOVERY_HTTP_TIMEOUT_SECONDS
        ) as resp:
            doc = json.loads(resp.read())
        return doc["jwks_uri"]
    except Exception as e:  # noqa: BLE001 - surface a single typed error
        raise OidcError(f"OIDC discovery failed for {discovery_url}: {e}")


def _resolve_jwks_url(issuer: str) -> str:
    explicit = os.getenv("OIDC_JWKS_URL")
    if explicit:
        return explicit
    return _discover_jwks_url(issuer)


def verify_bearer_token(token: str) -> dict:
    """Verify an OIDC JWT and return its (validated) claims.

    Verifies signature (via JWKS), ``iss``, ``exp`` and -- when ``OIDC_AUDIENCE``
    is configured -- ``aud``. Raises :class:`OidcError` on any failure.
    """
    issuer = os.getenv("OIDC_ISSUER")
    if not issuer:
        raise OidcError("OIDC_ISSUER is not configured")

    audience = os.getenv("OIDC_AUDIENCE")
    algorithms = [
        a.strip() for a in os.getenv("OIDC_ALGORITHMS", "RS256").split(",") if a.strip()
    ]

    jwks_url = _resolve_jwks_url(issuer)
    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    except Exception as e:  # noqa: BLE001
        raise OidcError(f"Failed to get signing key from JWKS: {e}")

    require = ["exp", "iss"]
    options: dict = {"verify_iss": True, "verify_exp": True}
    decode_kwargs: dict = {"issuer": issuer}
    if audience:
        require.append("aud")
        options["verify_aud"] = True
        decode_kwargs["audience"] = audience
    else:
        options["verify_aud"] = False
    options["require"] = require

    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            options=options,
            **decode_kwargs,
        )
    except Exception as e:  # noqa: BLE001
        raise OidcError(f"Bearer token verification failed: {e}")
