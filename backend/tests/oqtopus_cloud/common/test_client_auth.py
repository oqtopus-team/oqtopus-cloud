"""Unit tests for the in-app Q-API-Token resolver (common/auth/client.py).

The DB session is mocked (a fake row), so these exercise only the verification
logic: hash match, expiry, approved-status, and the 401-vs-403 mapping.
"""

from collections import namedtuple
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from argon2 import PasswordHasher

from oqtopus_cloud.common.auth import client as client_auth
from oqtopus_cloud.common.auth.frontend import AuthError, AuthorizationError
from oqtopus_cloud.common.models.user import UserStatus

UTC = ZoneInfo("UTC")
_ph = PasswordHasher()
# Weak params so the default hasher reports needs_rehash (to exercise rehash).
_weak_ph = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)

Row = namedtuple("Row", "id api_token_id api_token_hash api_token_expiration userstatus")


def _request(token):
    headers = {"q-api-token": token} if token is not None else {}
    return SimpleNamespace(headers=headers)


def _mock_db(monkeypatch, row):
    db = MagicMock()
    # The shared verifier queries ORM objects: db.execute(...).scalars().first()
    db.execute.return_value.scalars.return_value.first.return_value = row
    monkeypatch.setattr(client_auth, "_create_session", lambda **_kwargs: db)
    return db


def _row(secret, *, status=UserStatus.approved, expired=False, hasher=_ph):
    exp = datetime.now(UTC) + timedelta(days=-1 if expired else 90)
    return Row("demo@oqtopus.local", "tok-id", hasher.hash(secret), exp, status)


class TestResolveApiTokenIdentity:
    def test_valid_token_approved_returns_identity(self, monkeypatch):
        _mock_db(monkeypatch, _row("s3cret"))
        identity = client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))
        assert identity.user_id == "demo@oqtopus.local"

    def test_missing_header_is_401(self):
        with pytest.raises(AuthError, match="Missing"):
            client_auth.resolve_api_token_identity(_request(None))

    def test_malformed_token_is_401(self):
        with pytest.raises(AuthError, match="Malformed"):
            client_auth.resolve_api_token_identity(_request("no-dot-here"))

    def test_unknown_token_is_401(self, monkeypatch):
        _mock_db(monkeypatch, None)
        with pytest.raises(AuthError, match="Invalid API token"):
            client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))

    def test_wrong_secret_is_401(self, monkeypatch):
        _mock_db(monkeypatch, _row("the-real-secret"))
        with pytest.raises(AuthError, match="Invalid API token"):
            client_auth.resolve_api_token_identity(_request("tok-id.wrong-secret"))

    def test_expired_token_is_401(self, monkeypatch):
        _mock_db(monkeypatch, _row("s3cret", expired=True))
        with pytest.raises(AuthError, match="expired"):
            client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))

    def test_unapproved_user_is_403(self, monkeypatch):
        _mock_db(monkeypatch, _row("s3cret", status=UserStatus.unapproved))
        with pytest.raises(AuthorizationError, match="not approved"):
            client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))

    def test_approved_token_with_stale_hash_is_rehashed(self, monkeypatch):
        db = _mock_db(monkeypatch, _row("s3cret", hasher=_weak_ph))
        client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))
        db.commit.assert_called_once()

    def test_unapproved_user_with_stale_hash_is_not_rehashed(self, monkeypatch):
        # Regression: a request rejected by authorization (unapproved) must not
        # mutate the DB, even when the stored hash is stale.
        db = _mock_db(
            monkeypatch,
            _row("s3cret", status=UserStatus.unapproved, hasher=_weak_ph),
        )
        with pytest.raises(AuthorizationError):
            client_auth.resolve_api_token_identity(_request("tok-id.s3cret"))
        db.commit.assert_not_called()
