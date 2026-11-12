"""Shared Q-API-Token credential verification (single source of truth).

Both the on-prem in-app resolver (``common/auth/client.py``) and the AWS Lambda
authorizer (``lambda_auth/lambda_function.py``) verify the *same* DB-backed
``Q-API-Token``. Keeping that check in one place stops the two from drifting --
for example a security fix applied to one copy but not the other.

This function performs only *authentication* of the credential (parse, Argon2
verify, expiry) plus an opportunistic hash upgrade. Each caller layers its own
*authorization* on top (approved status; on AWS also MFA / Cognito mapping).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from sqlalchemy import select, update

from oqtopus_cloud.common.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_utc = ZoneInfo("UTC")
_ph = PasswordHasher()


class ApiTokenError(Exception):
    """A ``Q-API-Token`` could not be authenticated (maps to HTTP 401)."""


def parse_api_token(raw_token: str | None) -> tuple[str, str]:
    """Split a raw ``<id>.<secret>`` Q-API-Token without touching the DB.

    Kept separate from :func:`verify_api_token` so callers can reject a missing
    or malformed header cheaply, before opening a DB session.

    Returns:
        The ``(token_id, secret)`` pair.

    Raises:
        ApiTokenError: the token is missing or malformed.

    """
    if not raw_token:
        raise ApiTokenError("Missing Q-API-Token")
    try:
        token_id, secret = raw_token.split(".")
    except ValueError as e:
        raise ApiTokenError("Malformed Q-API-Token") from e
    return token_id, secret


def verify_api_token(db: Session, token_id: str, secret: str) -> User:
    """Authenticate a parsed Q-API-Token (``token_id``/``secret``) against the DB.

    On success returns the owning :class:`User`; the *credential* (secret + not
    expired) is verified, but **no DB mutation happens here**. The caller is
    responsible for *authorization* (e.g. approved status, and on AWS also
    MFA / Cognito existence) and must call :func:`rehash_api_token_if_needed`
    only once the request is fully accepted -- so a request that is ultimately
    rejected never rehashes/writes the DB.

    Returns:
        The authenticated token owner.

    Raises:
        ApiTokenError: the token is unknown, has a bad secret, or is expired.

    """
    user = (
        db.execute(select(User).where(User.api_token_id == token_id))
        .scalars()
        .first()
    )
    if user is None or user.api_token_hash is None:
        raise ApiTokenError("Invalid API token")

    try:
        _ph.verify(user.api_token_hash, secret)
    except VerifyMismatchError as e:
        raise ApiTokenError("Invalid API token") from e
    except (VerificationError, InvalidHash) as e:
        raise ApiTokenError("API token verification error") from e

    expiration = user.api_token_expiration
    if expiration is None or expiration.astimezone(_utc) < datetime.now(_utc):
        raise ApiTokenError("API token is expired")

    return user


def rehash_api_token_if_needed(
    db: Session, token_id: str, current_hash: str | None, secret: str
) -> None:
    """Opportunistically upgrade the stored Argon2 hash to current parameters.

    Call this **only after the request is fully authorized** (see
    :func:`verify_api_token`), so a request that is ultimately rejected
    (unapproved, MFA-disabled, Cognito user missing, ...) never mutates the DB.

    Takes primitives (not an ORM object) so the caller can close the
    credential-check session and run this in a fresh short-lived one -- keeping
    a DB connection off the hot path during any slow external authz (e.g. a
    Cognito lookup). The update is guarded on ``current_hash``, so a concurrent
    token rotation/deletion is not clobbered; it is a no-op when no upgrade is
    needed.
    """
    if current_hash is None or not _ph.check_needs_rehash(current_hash):
        return
    db.execute(
        update(User)
        .where(
            User.api_token_id == token_id,
            User.api_token_hash == current_hash,
        )
        .values(api_token_hash=_ph.hash(secret))
    )
    db.commit()
