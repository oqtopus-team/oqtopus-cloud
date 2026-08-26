"""Auth-seam tests for the Provider API middleware (AUTH_MODE dispatch).

These exercise ``oqtopus_cloud.provider.middleware`` via a real request through
the app. ``/hello`` is used because it needs no DB, so only the auth seam is
under test. ``verify_bearer_token`` is patched so no live IdP/JWKS is required.
"""

import pytest
from fastapi.testclient import TestClient

from oqtopus_cloud.common.auth.oidc import OidcError
from oqtopus_cloud.provider.lambda_function import app

client = TestClient(app)


@pytest.fixture
def oidc_mode(monkeypatch):
    """Run the middleware in OIDC machine-to-machine mode."""
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("PROVIDER_REQUIRED_SCOPE", "provider.write")


def test_local_mode_bypasses_auth(monkeypatch):
    """The existing ENV=local developer path needs no token."""
    monkeypatch.setenv("AUTH_MODE", "local")
    resp = client.get("/hello")
    assert resp.status_code == 200


def test_aws_mode_requires_no_bearer(monkeypatch):
    """In aws mode the API-gateway key is validated upstream; no token here."""
    monkeypatch.setenv("AUTH_MODE", "aws")
    resp = client.get("/hello")
    assert resp.status_code == 200


def test_oidc_missing_token_is_401(oidc_mode):
    resp = client.get("/hello")
    assert resp.status_code == 401


def test_oidc_invalid_token_is_401(oidc_mode, monkeypatch):
    def _raise(_token: str) -> dict:
        raise OidcError("bad token")

    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.machine.verify_bearer_token", _raise
    )
    resp = client.get("/hello", headers={"Authorization": "Bearer bad.jwt"})
    assert resp.status_code == 401


def test_oidc_missing_scope_is_401(oidc_mode, monkeypatch):
    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.machine.verify_bearer_token",
        lambda _token: {"azp": "oqtopus-engine", "scope": "openid"},
    )
    resp = client.get("/hello", headers={"Authorization": "Bearer good.jwt"})
    assert resp.status_code == 401


def test_oidc_valid_token_with_scope_passes(oidc_mode, monkeypatch):
    monkeypatch.setattr(
        "oqtopus_cloud.common.auth.machine.verify_bearer_token",
        lambda _token: {"azp": "oqtopus-engine", "scope": "provider.write"},
    )
    resp = client.get("/hello", headers={"Authorization": "Bearer good.jwt"})
    assert resp.status_code == 200
    assert resp.json() == {"message": "Hello World!!"}
