import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import TIMESTAMP, BigInteger, String, func, text
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
    group_id  (str)                 Group ID of the user.
    api_token_expiration (datetime) The expiration date of the API token.
    created_at (datetime)           The timestamp when the user was created.
    updated_at (datetime)           The timestamp when the user was last updated.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True)
    cognito_id: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    userstatus: Mapped[Optional[UserStatus]] = mapped_column(String(10), nullable=True)
    api_token_secret: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    organization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    group_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_token_expiration: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        nullable=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        nullable=True,
    )
