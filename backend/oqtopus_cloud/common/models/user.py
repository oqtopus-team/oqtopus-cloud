import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from oqtopus_cloud.common.models.base import (
    Base,
)

default_datetime = datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    """
    Represents a user in the system.

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

    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    cognito_id = Column(String, index=True)
    email = Column(String, index=True)
    username = Column(String, nullable=True)
    userstatus = Column(Integer, nullable=True)
    api_token_secret = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    purpose = Column(String, nullable=True)
    group_id = Column(String, nullable=True)
    require_mfa_reset = Column(Boolean, nullable=True)
    api_token_expiration = Column(DateTime, default=default_datetime)
    created_at = Column(DateTime, default=default_datetime)
    updated_at = Column(DateTime, default=default_datetime, onupdate=default_datetime)
    deleted_at = Column(DateTime, default=default_datetime)


class Error(Exception):
    pass


class JobNotFound(Error):
    """Exception raised when a job is not found.

    Args:
        Error (type): The base error class.

    """

    pass
