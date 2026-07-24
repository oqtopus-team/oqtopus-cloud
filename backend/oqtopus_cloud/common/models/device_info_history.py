import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models.base import Base
from oqtopus_cloud.common.models.common import TimestampMixin


class DeviceInfoHistory(TimestampMixin, Base):
    __tablename__ = "device_info_history"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "calibrated_at",
            name="uq_device_info_history_device_calibrated_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    calibrated_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(), nullable=False
    )
    n_qubits: Mapped[int] = mapped_column(nullable=False)
    n_couplings: Mapped[int] = mapped_column(nullable=False)
