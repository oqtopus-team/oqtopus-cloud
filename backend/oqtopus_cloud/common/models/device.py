import datetime
from enum import Enum
from typing import Literal, Optional

from sqlalchemy import TIMESTAMP, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models import Base

DeviceId = str


class DeviceType(Enum):
    QPU = "QPU"
    simulator = "simulator"


class DeviceStatus(Enum):
    Available = "available"
    Unavailable = "unavailable"


class Device(Base):
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

    id: Mapped[DeviceId] = mapped_column(
        String(64),
        primary_key=True,
    )
    device_type: Mapped[DeviceType] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[DeviceStatus] = mapped_column(
        String(64),
        nullable=False,
        default="unavailable",
    )
    available_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        nullable=True,
    )
    pending_jobs: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    n_qubits: Mapped[int] = mapped_column(
        nullable=False,
    )
    basis_gates: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    instructions: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    device_info: Mapped[str] = mapped_column(Text)
    calibrated_at: Mapped[datetime.datetime]
    description: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.CURRENT_TIMESTAMP()
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_onupdate=func.current_timestamp(),
    )
