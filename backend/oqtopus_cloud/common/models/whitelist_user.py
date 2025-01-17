import datetime
from typing import Optional
from sqlalchemy import Integer, String, Boolean, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class WhitelistUser(Base):
    """
    Represents a whitelist_users in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (int): The unique identifier of the whitelist user.
        group_id (str): The identifier of the group.
        email (str): The email of the whitelist user.
        username (str): The username of the whitelist user.
        organization (str): The organization name to which the whitelist user belongs.
        is_signup_completed (bool): Whether or not the whitelist user signup is completed.
    """

    __tablename__ = "whitelist_users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    group_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    organization: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    is_signup_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
    )
    deleted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
    )
