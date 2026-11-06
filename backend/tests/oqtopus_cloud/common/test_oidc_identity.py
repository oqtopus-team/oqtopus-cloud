"""Unit tests for the OIDC identity resolution (common/auth/frontend.py) and the
env->config adapter (common/auth/oidc.py).

Covers the two resolver modes:
  - "direct": a claim's value is the users.id (Keycloak / on-prem).
  - "cognito_sub": users.id is resolved via users.cognito_id == sub (Cognito).
"""

from types import SimpleNamespace

import pytest

from oqtopus_cloud.common.auth import frontend
from oqtopus_cloud.common.auth import oidc as cloud_oidc
from oqtopus_cloud.common.auth.frontend import (
    AuthError,
    AuthorizationError,
    _oidc_identity,
)
from oqtopus_cloud.common.auth.oidc import OidcError


def _request() -> SimpleNamespace:
    return SimpleNamespace(headers={"authorization": "Bearer dummy"})


def _patch_claims(monkeypatch, claims: dict) -> None:
    monkeypatch.setattr(frontend, "verify_bearer_token", lambda _token: claims)


# ── cognito_sub resolver ─────────────────────────────────────────────────────


class TestCognitoSubResolver:
    @pytest.fixture(autouse=True)
    def _mode(self, monkeypatch):
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "cognito_sub")

    def test_valid_sub_resolves_to_internal_id_and_email(self, monkeypatch):
        _patch_claims(monkeypatch, {"sub": "uuid-123", "token_use": "access"})
        monkeypatch.setattr(
            frontend,
            "resolve_user_by_cognito_id",
            lambda sub: ("u@example.com", "u@example.com") if sub == "uuid-123" else None,
        )
        identity = _oidc_identity(_request())
        assert identity.user_id == "u@example.com"
        assert identity.email == "u@example.com"
        assert identity.auth_method == "oidc"

    def test_missing_sub_is_401(self, monkeypatch):
        _patch_claims(monkeypatch, {"token_use": "access"})  # no sub
        with pytest.raises(AuthError, match="sub"):
            _oidc_identity(_request())

    def test_non_string_sub_is_401(self, monkeypatch):
        _patch_claims(monkeypatch, {"sub": ["uuid-123"]})
        with pytest.raises(AuthError, match="sub"):
            _oidc_identity(_request())

    def test_unknown_or_unapproved_user_is_403(self, monkeypatch):
        _patch_claims(monkeypatch, {"sub": "uuid-123"})
        monkeypatch.setattr(frontend, "resolve_user_by_cognito_id", lambda _sub: None)
        with pytest.raises(AuthorizationError):
            _oidc_identity(_request())

    def test_db_error_is_not_swallowed_into_401_or_403(self, monkeypatch):
        _patch_claims(monkeypatch, {"sub": "uuid-123"})

        def _boom(_sub):
            raise RuntimeError("db down")

        monkeypatch.setattr(frontend, "resolve_user_by_cognito_id", _boom)
        # Must propagate as a server error, not be mapped to AuthError (401/403).
        with pytest.raises(RuntimeError, match="db down"):
            _oidc_identity(_request())


# ── direct resolver (default; Keycloak / on-prem) ────────────────────────────


class TestDirectResolver:
    def test_claim_value_is_the_user_id(self, monkeypatch):
        monkeypatch.delenv("OIDC_IDENTITY_RESOLVER", raising=False)  # default direct
        monkeypatch.setenv("OIDC_USERNAME_CLAIM", "email")
        _patch_claims(monkeypatch, {"email": "u@example.com"})
        monkeypatch.setattr(frontend, "validate_user_status", lambda user_id: True)
        identity = _oidc_identity(_request())
        assert identity.user_id == "u@example.com"
        assert identity.auth_method == "oidc"

    def test_missing_claim_is_401(self, monkeypatch):
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "direct")
        monkeypatch.setenv("OIDC_USERNAME_CLAIM", "email")
        _patch_claims(monkeypatch, {"sub": "uuid-123"})  # no email
        with pytest.raises(AuthError, match="email"):
            _oidc_identity(_request())

    def test_unapproved_is_403(self, monkeypatch):
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "direct")
        monkeypatch.setenv("OIDC_USERNAME_CLAIM", "email")
        _patch_claims(monkeypatch, {"email": "u@example.com"})
        monkeypatch.setattr(frontend, "validate_user_status", lambda user_id: False)
        with pytest.raises(AuthorizationError):
            _oidc_identity(_request())


class TestResolverValidation:
    def test_unknown_resolver_is_rejected(self, monkeypatch):
        # A typo must fail closed, not silently fall back to "direct".
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "cognito_sbu")
        _patch_claims(monkeypatch, {"sub": "uuid-123", "email": "u@example.com"})
        with pytest.raises(AuthError, match="Unsupported OIDC_IDENTITY_RESOLVER"):
            _oidc_identity(_request())


# ── env -> OidcProviderConfig adapter ────────────────────────────────────────


class TestConfigFromEnv:
    @pytest.fixture(autouse=True)
    def _clean(self, monkeypatch):
        for var in (
            "OIDC_AUDIENCE",
            "OIDC_CLIENT_ID",
            "OIDC_ALLOW_ANY_AUDIENCE",
            "OIDC_TOKEN_USE",
            "OIDC_CLIENT_ID_CLAIM",
            "OIDC_JWKS_URL",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("OIDC_ISSUER", "https://cognito-idp.r.amazonaws.com/pool")

    def test_client_id_binding_without_audience(self, monkeypatch):
        monkeypatch.setenv("OIDC_CLIENT_ID", "app-client-123")
        monkeypatch.setenv("OIDC_TOKEN_USE", "access")
        cfg = cloud_oidc._config_from_env()
        assert cfg.client_id == "app-client-123"
        assert cfg.token_use == "access"
        assert cfg.audience is None

    def test_client_id_comma_list(self, monkeypatch):
        monkeypatch.setenv("OIDC_CLIENT_ID", "a, b ,c")
        cfg = cloud_oidc._config_from_env()
        assert cfg.client_id == ["a", "b", "c"]

    def test_no_binding_is_error(self):
        # Neither OIDC_AUDIENCE nor OIDC_CLIENT_ID nor allow-any -> fail-closed.
        with pytest.raises(OidcError, match="no token binding"):
            cloud_oidc._config_from_env()

    def test_audience_binding_still_works(self, monkeypatch):
        monkeypatch.setenv("OIDC_AUDIENCE", "oqtopus-user-api")
        cfg = cloud_oidc._config_from_env()
        assert cfg.audience == "oqtopus-user-api"
        assert cfg.client_id is None
