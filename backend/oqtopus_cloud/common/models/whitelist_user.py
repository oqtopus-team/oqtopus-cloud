import datetime
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, String, func, text
from sqlalchemy.dialects.mysql import BIGINT
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
        created_at (datetime): The timestamp when the whitelist user was created.
        updated_at (datetime): The timestamp when the whitelist user was last updated.
    """

    __tablename__ = "whitelist_users"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        unique=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    group_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_signup_completed: Mapped[Boolean] = mapped_column(
        Boolean,
        server_default=text("0"),
        nullable=True,
    )
    username: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    organization: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        nullable=True,
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
