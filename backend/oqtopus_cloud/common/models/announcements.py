import datetime

from sqlalchemy import Boolean, Integer, String
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
        Integer,
        primary_key=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
    )
    content: Mapped[str]
    start_time: Mapped[datetime.datetime] = mapped_column(DateTimeTz())
    end_time: Mapped[datetime.datetime] = mapped_column(DateTimeTz())
    publishable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
