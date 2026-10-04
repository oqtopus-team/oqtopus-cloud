"""401 (authn) vs 403 (authz) contract for the User-API auth middleware.

These exercise the OIDC branch of ``resolve_identity`` via a real request. All
cases fail in the middleware before routing, so no DB is needed. Token
verification and the approved-status check are patched.
"""

import pytest
from fastapi.testclient import TestClient

from oqtopus_cloud.common.auth.oidc import OidcError
from oqtopus_cloud.user.lambda_function import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def oidc_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_USERNAME_CLAIM", "email")


def test_oidc_missing_token_is_401(oidc_mode):
    resp = client.get("/devices")
    assert resp.status_code == 401


def test_oidc_invalid_token_is_401(oidc_mode, monkeypatch):
    def _raise(_token: str) -> dict:
        raise OidcError("bad token")

    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.frontend.verify_bearer_token", _raise
    )
    resp = client.get("/devices", headers={"Authorization": "Bearer bad.jwt"})
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_oidc_authenticated_but_unapproved_is_403(oidc_mode, monkeypatch):
    # Valid token, but the user is not approved in the DB -> 403, not 401
    # (re-authenticating would not help; the SPA must not bounce to login).
    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.frontend.verify_bearer_token",
        lambda _token: {"email": "u@example.com"},
    )
    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.frontend.validate_user_status",
        lambda **_kwargs: False,
    )
    resp = client.get("/devices", headers={"Authorization": "Bearer good.jwt"})
    assert resp.status_code == 403
