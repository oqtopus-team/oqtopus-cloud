import datetime
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column


def current_time_utc():
    return datetime.datetime.now(datetime.timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=current_time_utc,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        default=current_time_utc,
        onupdate=current_time_utc,
    )
