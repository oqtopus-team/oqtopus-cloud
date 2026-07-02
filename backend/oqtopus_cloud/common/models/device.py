import datetime
from typing import Optional

from sqlalchemy import String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.common import TimestampMixin


class Device(Base, TimestampMixin):
    """
    Represents a device in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (str): The unique identifier of the device.
        device_type (str): The type of the device (QPU or simulator).
        status (str): The status of the device (AVAILABLE or NOT_AVAILABLE).
        available_at (datetime): The date and time when the device is scheduled to restart.
        pending_jobs (int): The number of pending jobs for the device.
        n_qubits (int): The number of qubits of the device.
        basis_gates (str): The basis gates supported by the device.
        instructions (str): The supported instructions of the device.
        device_info (str): The infomation of the device.
        calibrated_at (datetime): The date and time when the device was last calibrated.
        description (str): The description of the device.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    device_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="QPU",
        server_default="QPU",
    )
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="available",
        server_default="available",
    )
    available_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTimeTz(),
        nullable=True,
    )
    pending_jobs: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    n_qubits: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    basis_gates: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    instructions: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    # NOT NULL by design (the Alembic migration is the source of truth): API
    # handlers substitute "{}" for missing values before insert (see Lambda
    # handlers).
    device_info: Mapped[str] = mapped_column(Text, nullable=False)
    calibrated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTimeTz(), nullable=True
    )
    description: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
