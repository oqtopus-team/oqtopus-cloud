"""Auth contract for the Admin-API middleware and identity resolution.

The Admin API differs from the User API: in ``aws`` mode it reads the Cognito
*authorizer* claims (``cognito:username``), and in ``oidc`` mode authorization is
"holds the configured admin role" rather than a DB approval gate.

Deny paths are exercised end-to-end through the middleware (they fail before
routing, so no DB is needed). The allow path and the role/claim logic are
unit-tested directly on ``resolve_admin_identity`` to avoid needing a DB.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.requests import Request

from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.common.auth.admin import (
    _extract_roles,
    resolve_admin_identity,
)
from oqtopus_cloud.common.auth.frontend import AuthError, AuthorizationError
from oqtopus_cloud.common.auth.oidc import OidcError
from oqtopus_cloud.common.models.user import User

client = TestClient(app, raise_server_exceptions=False)


def _seed_user(test_db, user_id: str = "email_1") -> None:
    test_db.add(
        User(
            id=user_id,
            cognito_id="cog_1",
            email=user_id,
            display_name="op",
            userstatus="approved",
            organization="org",
            group_id="g1",
            available_devices="[]",
            api_token_id=None,
            api_token_hash=None,
            api_token_expiration=None,
            created_at=datetime(2024, 3, 4, 12, 34, 57),
            updated_at=datetime(2024, 3, 4, 12, 34, 58),
        )
    )
    test_db.commit()


@pytest.fixture
def oidc_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("ADMIN_REQUIRED_ROLE", "oqtopus-admin")


def _request(headers: dict | None = None, aws_event: dict | None = None) -> Request:
    scope: dict = {
        "type": "http",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
    }
    if aws_event is not None:
        scope["aws.event"] = aws_event
    return Request(scope)


def _patch_claims(monkeypatch, claims: dict) -> None:
    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.admin.verify_bearer_token", lambda _t: claims
    )


# ── middleware deny paths (end-to-end, no DB) ────────────────────────────────


class TestMiddlewareDeny:
    def test_oidc_missing_token_is_401(self, oidc_mode):
        resp = client.get("/users")
        assert resp.status_code == 401

    def test_oidc_invalid_token_is_401(self, oidc_mode, monkeypatch):
        def _raise(_token: str) -> dict:
            raise OidcError("bad token")

        monkeypatch.setattr(
            "oqtopus_cloud.common.auth.admin.verify_bearer_token", _raise
        )
        resp = client.get("/users", headers={"Authorization": "Bearer bad.jwt"})
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate") == "Bearer"

    def test_oidc_authenticated_without_admin_role_is_403(self, oidc_mode, monkeypatch):
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["user"]}},
        )
        resp = client.get("/users", headers={"Authorization": "Bearer ok.jwt"})
        assert resp.status_code == 403

    def test_oidc_unset_required_role_is_500(self, monkeypatch):
        # A fail-closed configuration error: oidc mode with no ADMIN_REQUIRED_ROLE
        # must not authorize anyone, and must be loud (500), not a silent 403.
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.delenv("ADMIN_REQUIRED_ROLE", raising=False)
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["oqtopus-admin"]}},
        )
        resp = client.get("/users", headers={"Authorization": "Bearer ok.jwt"})
        assert resp.status_code == 500


# ── oidc identity resolution (unit) ──────────────────────────────────────────


class TestOidcResolve:
    @pytest.fixture(autouse=True)
    def _mode(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("ADMIN_REQUIRED_ROLE", "oqtopus-admin")

    def test_valid_token_with_role_resolves(self, monkeypatch):
        _patch_claims(
            monkeypatch,
            {
                "preferred_username": "op",
                "email": "op@example.com",
                "realm_access": {"roles": ["oqtopus-admin", "user"]},
            },
        )
        identity = resolve_admin_identity(_request({"authorization": "Bearer x"}))
        assert identity.user_id == "op"
        assert identity.email == "op@example.com"
        assert identity.auth_method == "oidc"

    def test_missing_role_is_authorization_error(self, monkeypatch):
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["user"]}},
        )
        with pytest.raises(AuthorizationError):
            resolve_admin_identity(_request({"authorization": "Bearer x"}))

    def test_missing_principal_claim_is_401(self, monkeypatch):
        _patch_claims(monkeypatch, {"realm_access": {"roles": ["oqtopus-admin"]}})
        with pytest.raises(AuthError, match="preferred_username"):
            resolve_admin_identity(_request({"authorization": "Bearer x"}))

    def test_custom_principal_and_roles_claim(self, monkeypatch):
        monkeypatch.setenv("ADMIN_PRINCIPAL_CLAIM", "email")
        monkeypatch.setenv("ADMIN_ROLES_CLAIM", "cognito:groups")
        monkeypatch.setenv("ADMIN_REQUIRED_ROLE", "admins")
        _patch_claims(
            monkeypatch,
            {"email": "op@example.com", "cognito:groups": ["admins"]},
        )
        identity = resolve_admin_identity(_request({"authorization": "Bearer x"}))
        assert identity.user_id == "op@example.com"

    def test_unset_required_role_raises_runtime_error(self, monkeypatch):
        monkeypatch.delenv("ADMIN_REQUIRED_ROLE", raising=False)
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["oqtopus-admin"]}},
        )
        with pytest.raises(RuntimeError, match="ADMIN_REQUIRED_ROLE"):
            resolve_admin_identity(_request({"authorization": "Bearer x"}))

    def test_missing_authorization_header_is_401(self):
        with pytest.raises(AuthError):
            resolve_admin_identity(_request({}))


# ── aws / local modes (unit) ─────────────────────────────────────────────────


class TestAwsAndLocal:
    def test_aws_reads_cognito_username(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "aws")
        monkeypatch.setenv("CLIENT_COGNITO_USER_POOL_ID", "ap-northeast-1_ABC")
        event = {
            "requestContext": {"authorizer": {"claims": {"cognito:username": "root"}}}
        }
        identity = resolve_admin_identity(_request(aws_event=event))
        assert identity.user_id == "root"
        assert identity.region == "ap-northeast-1"
        assert identity.auth_method == "aws"

    def test_aws_missing_authorizer_raises_keyerror(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "aws")
        with pytest.raises(KeyError):
            # No aws.event in scope -> KeyError (middleware maps this to 500).
            resolve_admin_identity(_request())

    def test_local_mode_fixed_identity(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "local")
        identity = resolve_admin_identity(_request())
        assert identity.user_id == "admin"
        assert identity.auth_method == "local"

    def test_unknown_mode_is_autherror(self, monkeypatch):
        monkeypatch.setenv("AUTH_MODE", "bogus")
        with pytest.raises(AuthError, match="Unknown AUTH_MODE"):
            resolve_admin_identity(_request())


# ── role extraction (pure) ───────────────────────────────────────────────────


class TestExtractRoles:
    def test_nested_realm_access_roles(self):
        claims = {"realm_access": {"roles": ["a", "b"]}}
        assert _extract_roles(claims, "realm_access.roles") == ["a", "b"]

    def test_top_level_colon_claim(self):
        assert _extract_roles({"cognito:groups": ["admins"]}, "cognito:groups") == [
            "admins"
        ]

    def test_single_string_value_becomes_list(self):
        assert _extract_roles({"role": "admin"}, "role") == ["admin"]

    def test_missing_path_is_empty(self):
        assert _extract_roles({"realm_access": {}}, "realm_access.roles") == []

    def test_non_string_entries_are_dropped(self):
        claims = {"roles": ["a", 1, None, "b"]}
        assert _extract_roles(claims, "roles") == ["a", "b"]


# ── end-to-end OIDC on an AWS-less deployment ────────────────────────────────


class TestOidcEndToEnd:
    """OIDC requests that reach a route without any AWS context or correlation
    header -- the shape of an on-prem deployment behind oauth2-proxy/nginx."""

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch):
        # ENV != local (pytest-env sets it to "local" by default) so the
        # middleware takes the non-local correlation-id path, with no AWS
        # context and no X-Correlation-Id header -- it must not KeyError.
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("AUTH_MODE", "oidc")
        monkeypatch.setenv("ADMIN_REQUIRED_ROLE", "oqtopus-admin")

    def test_admin_role_token_reaches_route_without_aws_context(
        self, monkeypatch, test_db
    ):
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["oqtopus-admin"]}},
        )
        resp = client.get("/users", headers={"Authorization": "Bearer ok.jwt"})
        assert resp.status_code == 200
        # A correlation id was generated (not carried in), not a crash.
        assert resp.headers.get("X-Correlation-Id")

    def test_oidc_delete_is_501_and_leaves_db_untouched(self, monkeypatch, test_db):
        # P1: deletion is unsupported in oidc mode and must be refused BEFORE any
        # DB mutation, so the row survives (no partial success).
        _seed_user(test_db, "email_1")
        _patch_claims(
            monkeypatch,
            {"preferred_username": "op", "realm_access": {"roles": ["oqtopus-admin"]}},
        )
        resp = client.delete("/users/email_1", headers={"Authorization": "Bearer ok.jwt"})
        assert resp.status_code == 501
        still_there = test_db.execute(
            select(User).where(User.id == "email_1")
        ).scalars().first()
        assert still_there is not None
