import datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    DateTime,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class Announcement(Base):
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
        BigInteger,
        primary_key=True,
        unique=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    end_time: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    publishable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
