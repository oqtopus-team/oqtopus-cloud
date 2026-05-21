from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.common import TimestampMixin


class WhitelistUser(Base, TimestampMixin):
    """
    Represents a whitelist_users in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (int): The unique identifier of the whitelist user.
        group_id (str): The identifier of the group.
        email (str): The email of the whitelist user.
        display_name (str): The display name of the whitelist user.
        organization (str): The organization name to which the whitelist user belongs.
        is_signup_completed (bool): Whether or not the whitelist user signup is completed.
        available_devices (string): List of devices allowed for the user.
        created_at (datetime): The timestamp when the whitelist user was created.
        updated_at (datetime): The timestamp when the whitelist user was last updated.
    """

    __tablename__ = "whitelist_users"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BIGINT(unsigned=True), "mysql"),
        primary_key=True,
        autoincrement=True,
    )
    group_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    organization: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    is_signup_completed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
        server_default=text("0"),
    )
    available_devices: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
