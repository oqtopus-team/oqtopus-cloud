import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.common import TimestampMixin
from oqtopus_cloud.common.model_util import DateTimeTz


class Announcement(Base, TimestampMixin):
    """
    Represents an announcement in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (str): The unique identifier of announcement.
        title (str): The title of the announcement.
        content (str): The content of of the announcement.
        start_time (datetime): Announcement's publishing start time.
        end_time (datetime): Announcement's publishing end time.
        publishable (bool): Flag indicating if announcement can be published.
        created_at (datetime): The timestamp when the announcement was created.
        updated_at (datetime): The timestamp when the announcement was last updated.
    """

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(
        Integer().with_variant(BIGINT(unsigned=True), "mysql"),
        primary_key=True,
        autoincrement=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTimeTz(), nullable=True
    )
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTimeTz(), nullable=True
    )
    publishable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
