"""Unit tests for the shared Q-API-Token verifier (common/auth/api_token.py).

This is the single source of truth used by both the in-app resolver and the AWS
Lambda authorizer. The key invariant pinned here: ``verify_api_token`` performs
no DB mutation, and the opportunistic rehash (``rehash_api_token_if_needed``) is
a caller-controlled step run only after a request is fully authorized.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from argon2 import PasswordHasher

from oqtopus_cloud.common.auth.api_token import (
    ApiTokenError,
    parse_api_token,
    rehash_api_token_if_needed,
    verify_api_token,
)

UTC = ZoneInfo("UTC")
_ph = PasswordHasher()
# Deliberately weak params so the module's default hasher reports needs_rehash.
_weak_ph = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


def _user(secret, *, expired=False, hasher=_ph):
    exp = datetime.now(UTC) + timedelta(days=-1 if expired else 90)
    return SimpleNamespace(
        id="demo@oqtopus.local",
        api_token_id="tok-id",
        api_token_hash=hasher.hash(secret),
        api_token_expiration=exp,
    )


def _db(user):
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = user
    return db


def test_parse_valid():
    assert parse_api_token("tok-id.s3cret") == ("tok-id", "s3cret")


@pytest.mark.parametrize("raw", [None, "", "no-dot-here"])
def test_parse_missing_or_malformed_raises(raw):
    with pytest.raises(ApiTokenError):
        parse_api_token(raw)


def test_valid_token_returns_user():
    user = _user("s3cret")
    assert verify_api_token(_db(user), "tok-id", "s3cret") is user


def test_unknown_token_raises():
    with pytest.raises(ApiTokenError, match="Invalid"):
        verify_api_token(_db(None), "tok-id", "s3cret")


def test_wrong_secret_raises():
    with pytest.raises(ApiTokenError, match="Invalid"):
        verify_api_token(_db(_user("the-real-secret")), "tok-id", "wrong")


def test_expired_token_raises():
    with pytest.raises(ApiTokenError, match="expired"):
        verify_api_token(_db(_user("s3cret", expired=True)), "tok-id", "s3cret")


def test_verify_never_commits_even_with_stale_hash():
    # verify_api_token authenticates only; it must not mutate the DB, even when
    # the stored hash is stale. The rehash is a separate, caller-controlled step.
    db = _db(_user("s3cret", hasher=_weak_ph))
    verify_api_token(db, "tok-id", "s3cret")
    db.commit.assert_not_called()


def test_rehash_if_needed_commits_for_stale_hash():
    db = MagicMock()
    rehash_api_token_if_needed(db, "tok-id", _weak_ph.hash("s3cret"), "s3cret")
    db.commit.assert_called_once()


def test_rehash_if_needed_is_noop_for_fresh_hash():
    db = MagicMock()
    rehash_api_token_if_needed(db, "tok-id", _ph.hash("s3cret"), "s3cret")
    db.commit.assert_not_called()


def test_rehash_if_needed_is_noop_for_none_hash():
    db = MagicMock()
    rehash_api_token_if_needed(db, "tok-id", None, "s3cret")
    db.commit.assert_not_called()
