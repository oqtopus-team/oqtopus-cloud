import datetime
from sqlalchemy.orm import mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime
from oqtopus_cloud.common.models.base import (
    Base,
)

default_datetime = datetime.datetime.now(datetime.timezone.utc)


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
    deleted_at (datetime)           The timestamp when the user was deleted.
    """

    __tablename__ = "users"
    id = mapped_column(Integer, primary_key=True, index=True)
    cognito_id = mapped_column(String, index=True)
    email = mapped_column(String, index=True)
    username = mapped_column(String, nullable=True)
    userstatus = mapped_column(Integer, nullable=True)
    api_token_secret = mapped_column(String, nullable=True)
    organization = mapped_column(String, nullable=True)
    purpose = mapped_column(String, nullable=True)
    group_id = mapped_column(String, nullable=True)
    require_mfa_reset = mapped_column(Boolean, nullable=True)
    api_token_expiration = mapped_column(DateTime, default=default_datetime)
    created_at = mapped_column(DateTime, default=default_datetime)
    updated_at = mapped_column(
        DateTime, default=default_datetime, onupdate=default_datetime
    )
    deleted_at = mapped_column(DateTime, default=default_datetime)


class Error(Exception):
    pass


class JobNotFound(Error):
    """Exception raised when a job is not found.

    Args:
        Error (type): The base error class.

    """

    pass
