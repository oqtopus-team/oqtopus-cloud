import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.common import TimestampMixin, current_time_utc


class UserStatus(str, Enum):
    approved = "approved"
    unapproved = "unapproved"
    suspended = "suspended"


class MFAStatus(str, Enum):
    enabled = "enabled"
    disabled = "disabled"


class User(Base, TimestampMixin):
    """
    Represents a users in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
    id (int)                        The unique identifier of the user.
    cognito_id (str)                Cognito ID of the user.
    user_identifier (str)           Cognito username of the user.
    email (str)                     Email of the user.
    display_name (str):             The display name of the user.
    username (str)                  Username of the user.
    userstatus (int)                Status of the user.
    organization (str)              Organization of the user.
    group_id  (str)                 Group ID of the user.
    available_devices (str)         List of devices which user has permission to access
    mfa_status (str)                MFA status of the user 'enabled' / 'disabled', default is 'disabled '.
    api_token_id (str)              API token unique identifier.
    api_token_hash (str)            API token secret hash.
    api_token_expiration (datetime) The expiration date of the API token.
    created_at (datetime)           The timestamp when the user was created.
    updated_at (datetime)           The timestamp when the user was last updated.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cognito_id: Mapped[str] = mapped_column(String, index=True)
    user_identifier: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    userstatus: Mapped[Optional[UserStatus]] = mapped_column(String, nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    group_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    available_devices: Mapped[str] = mapped_column(String, nullable=True)
    mfa_status: Mapped[MFAStatus] = mapped_column(
        String, default=MFAStatus.disabled, nullable=False
    )
    api_token_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    api_token_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_token_expiration: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, default=current_time_utc, nullable=True
    )
