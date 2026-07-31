import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models.base import Base
from oqtopus_cloud.common.models.common import TimestampMixin


class DeviceInfoHistory(TimestampMixin, Base):
    __tablename__ = "device_info_history"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calibrated_at: Mapped[datetime.datetime] = mapped_column(
        DateTimeTz(), primary_key=True
    )
    n_qubits: Mapped[int] = mapped_column(nullable=False)
    n_couplings: Mapped[int] = mapped_column(nullable=False)
