import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)

default_datetime = datetime.datetime.now(datetime.timezone.utc)


class UserStatus(str, Enum):
    approved = "approved"
    unapproved = "unapproved"
    suspended = "suspended"


class User(Base):
    """
    Represents a users in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
    id (int)                        The unique identifier of the user.
    cognito_id (str)                Cognito ID of the user.
    email (str)                     Email of the user.
    username (str)                  Username of the user.
    userstatus (int)                Status of the user.
    api_token_secret (str)          API token secret of the user.
    organization (str)              Organization of the user.
    purpose (str)                   Purpose of the user.
    group_id  (str)                 Group ID of the user.
    require_mfa_reset (bool)        Whether the user requires MFA reset.
    api_token_expiration (datetime) The expiration date of the API token.
    created_at (datetime)           The timestamp when the user was created.
    updated_at (datetime)           The timestamp when the user was last updated.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cognito_id: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    userstatus: Mapped[Optional[UserStatus]] = mapped_column(String, nullable=True)
    api_token_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    group_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    require_mfa_reset: Mapped[bool] = mapped_column(Boolean, nullable=True)
    api_token_expiration: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=default_datetime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=default_datetime
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=default_datetime, onupdate=default_datetime
    )
