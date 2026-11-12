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
    user_auth_policy,
    validate_user_auth_policy,
)
from oqtopus_cloud.common.auth.oidc import OidcError
from oqtopus_cloud.common.models.user import MFAStatus


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
            lambda sub: (
                ("u@example.com", "u@example.com", MFAStatus.enabled)
                if sub == "uuid-123"
                else None
            ),
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


# ── USER_AUTH_POLICY on the cognito_sub (access-token) path ──────────────────


class TestCognitoPolicyMfaOnAccessToken:
    """USER_AUTH_POLICY=cognito enforces DB MFA on the Cognito access-token path;
    USER_AUTH_POLICY=oidc (on-prem) delegates MFA to the IdP and does not."""

    @pytest.fixture(autouse=True)
    def _resolver(self, monkeypatch):
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "cognito_sub")

    def _stub(self, monkeypatch, mfa):
        _patch_claims(monkeypatch, {"sub": "uuid-123", "token_use": "access"})
        monkeypatch.setattr(
            frontend,
            "resolve_user_by_cognito_id",
            lambda _sub: ("u@example.com", "u@example.com", mfa),
        )

    def test_cognito_policy_mfa_enabled_succeeds(self, monkeypatch):
        monkeypatch.setenv("USER_AUTH_POLICY", "cognito")
        self._stub(monkeypatch, MFAStatus.enabled)
        assert _oidc_identity(_request()).user_id == "u@example.com"

    def test_cognito_policy_mfa_disabled_is_403(self, monkeypatch):
        monkeypatch.setenv("USER_AUTH_POLICY", "cognito")
        self._stub(monkeypatch, MFAStatus.disabled)
        with pytest.raises(AuthorizationError, match="MFA"):
            _oidc_identity(_request())

    def test_oidc_policy_ignores_mfa(self, monkeypatch):
        # On-prem: an MFA-disabled DB row is fine; the IdP (Keycloak) gates MFA.
        monkeypatch.setenv("USER_AUTH_POLICY", "oidc")
        self._stub(monkeypatch, MFAStatus.disabled)
        assert _oidc_identity(_request()).user_id == "u@example.com"


class TestUserAuthPolicyValidation:
    """Fail-closed startup validation of USER_AUTH_POLICY under AUTH_MODE=oidc."""

    def test_default_is_empty(self, monkeypatch):
        monkeypatch.delenv("USER_AUTH_POLICY", raising=False)
        assert user_auth_policy() == ""

    def test_noop_when_not_oidc_mode(self, monkeypatch):
        monkeypatch.delenv("AUTH_MODE", raising=False)  # ENV=local -> local mode
        monkeypatch.delenv("USER_AUTH_POLICY", raising=False)
        validate_user_auth_policy()  # no raise

    def test_unset_under_oidc_fails(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.delenv("USER_AUTH_POLICY", raising=False)
        with pytest.raises(RuntimeError, match="USER_AUTH_POLICY"):
            validate_user_auth_policy()

    def test_unknown_value_under_oidc_fails(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("USER_AUTH_POLICY", "cognitoo")
        with pytest.raises(RuntimeError):
            validate_user_auth_policy()

    def test_cognito_requires_cognito_sub_resolver(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("USER_AUTH_POLICY", "cognito")
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "direct")
        monkeypatch.setenv("CLIENT_COGNITO_USER_POOL_ID", "ap-northeast-1_x")
        with pytest.raises(RuntimeError, match="cognito_sub"):
            validate_user_auth_policy()

    def test_cognito_requires_pool_id(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("USER_AUTH_POLICY", "cognito")
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "cognito_sub")
        monkeypatch.delenv("CLIENT_COGNITO_USER_POOL_ID", raising=False)
        with pytest.raises(RuntimeError, match="CLIENT_COGNITO_USER_POOL_ID"):
            validate_user_auth_policy()

    def test_valid_cognito_config_passes(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("USER_AUTH_POLICY", "cognito")
        monkeypatch.setenv("OIDC_IDENTITY_RESOLVER", "cognito_sub")
        monkeypatch.setenv("CLIENT_COGNITO_USER_POOL_ID", "ap-northeast-1_x")
        validate_user_auth_policy()  # no raise

    def test_valid_oidc_policy_passes(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("USER_AUTH_POLICY", "oidc")
        validate_user_auth_policy()  # no raise


class TestResolveIdentityEnforcesPolicyPerRequest:
    """resolve_identity must validate USER_AUTH_POLICY on every oidc request,
    independent of the startup event (Lambda runs with lifespan off), before it
    dispatches to either the Bearer or the Q-API-Token resolver."""

    @pytest.fixture(autouse=True)
    def _oidc(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")

    @staticmethod
    def _req(headers):
        return SimpleNamespace(headers=headers)

    def test_unset_policy_fails_before_bearer_dispatch(self, monkeypatch):
        monkeypatch.delenv("USER_AUTH_POLICY", raising=False)
        # No verify_bearer_token patch: if it reached the Bearer resolver it
        # would fail differently. It must fail in validation first.
        with pytest.raises(RuntimeError, match="USER_AUTH_POLICY"):
            frontend.resolve_identity(self._req({"authorization": "Bearer x"}))

    def test_unset_policy_fails_before_qapi_dispatch(self, monkeypatch):
        monkeypatch.delenv("USER_AUTH_POLICY", raising=False)
        # No DB mock: reaching the Q-API-Token resolver would touch the DB. It
        # must fail in validation first, proving neither path needs startup.
        with pytest.raises(RuntimeError, match="USER_AUTH_POLICY"):
            frontend.resolve_identity(self._req({"q-api-token": "tok.secret"}))

    def test_unknown_policy_fails(self, monkeypatch):
        monkeypatch.setenv("USER_AUTH_POLICY", "bogus")
        with pytest.raises(RuntimeError):
            frontend.resolve_identity(self._req({"authorization": "Bearer x"}))
