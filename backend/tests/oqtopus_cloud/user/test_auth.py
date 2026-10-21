"""401 (authn) vs 403 (authz) contract for the User-API auth middleware.

These exercise the OIDC branch of ``resolve_identity`` via a real request. All
cases fail in the middleware before routing, so no DB is needed. Token
verification and the approved-status check are patched.
"""

import pytest
from fastapi.testclient import TestClient

from oqtopus_cloud.common.auth.frontend import Identity
from oqtopus_cloud.common.auth.oidc import OidcError
from oqtopus_cloud.user.lambda_function import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def oidc_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "oidc")
    monkeypatch.setenv("OIDC_USERNAME_CLAIM", "email")
    # Tests that route into a handler (not just the middleware) emit a Powertools
    # metric on completion; give it a namespace so that does not 500.
    monkeypatch.setenv("POWERTOOLS_METRICS_NAMESPACE", "test")


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


def test_qapi_token_header_routes_to_token_path(oidc_mode):
    # A Q-API-Token header must be handled by the DB-backed token resolver, not
    # the OIDC path. A malformed token fails there (401) before any DB access,
    # which confirms the dispatch without needing a seeded token.
    resp = client.get("/devices", headers={"Q-API-Token": "no-dot-here"})
    assert resp.status_code == 401
    # A token (non-Bearer) failure must NOT advertise a Bearer challenge, or the
    # CLI would be misdirected to an OIDC flow it does not use.
    assert "WWW-Authenticate" not in resp.headers


def test_api_token_caller_cannot_issue_api_token(oidc_mode, monkeypatch):
    # A caller authenticated *with* a Q-API-Token must not mint a fresh token
    # (that would let a leaked token renew itself forever) -> 403. The guard
    # returns before any DB use, so get_db is overridden only to satisfy
    # dependency resolution (FastAPI resolves it before the handler body runs).
    from unittest.mock import MagicMock

    from oqtopus_cloud.common.session import get_db

    monkeypatch.setattr(
        "oqtopus_cloud.user.middleware.resolve_identity",
        lambda _request: Identity(user_id="u@example.com", auth_method="api_token"),
    )
    app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        resp = client.post("/api-token")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 403


def test_oidc_caller_may_reach_api_token_issuance(oidc_mode, monkeypatch):
    # An interactive (OIDC) caller is allowed past the issuance guard; it then
    # reaches the DB layer. Override get_db so no live database is needed: an
    # empty result -> 404 (user not found), proving the auth-method guard did
    # NOT reject it with 403.
    from unittest.mock import MagicMock

    from oqtopus_cloud.common.session import get_db

    monkeypatch.setattr(
        "oqtopus_cloud.user.middleware.resolve_identity",
        lambda _request: Identity(user_id="u@example.com", auth_method="oidc"),
    )
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    try:
        resp = client.post("/api-token")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert resp.status_code == 404


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
