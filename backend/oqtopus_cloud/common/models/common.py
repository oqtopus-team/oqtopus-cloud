import datetime
from sqlalchemy.orm import Mapped, mapped_column
from oqtopus_cloud.common.model_util import DateTimeTz


def current_time_utc():
    return datetime.datetime.now(datetime.timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(),
        nullable=True,
        default=current_time_utc,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(),
        nullable=True,
        default=current_time_utc,
        onupdate=current_time_utc,
    )
