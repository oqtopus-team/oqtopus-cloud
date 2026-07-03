import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from oqtopus_cloud.common.model_util import DateTimeTz


def current_time_utc():
    return datetime.datetime.now(datetime.timezone.utc)


class TimestampMixin:
    # NOTE: updated_at uses Python-side `onupdate=current_time_utc` rather than
    # MySQL's `ON UPDATE CURRENT_TIMESTAMP` for portability. The auto-update
    # behavior works as long as writes go through SQLAlchemy ORM.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(),
        nullable=True,
        default=current_time_utc,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(),
        nullable=True,
        default=current_time_utc,
        onupdate=current_time_utc,
        server_default=func.now(),
    )
