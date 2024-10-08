import datetime
import enum

from sqlalchemy import (
    Enum,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class Device(Base):
    """
    Represents a device in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (str): The unique identifier of the device.
        device_type (str): The type of the device (QPU or simulator).
        status (str): The status of the device (AVAILABLE or NOT_AVAILABLE).
        restart_at (datetime): The date and time when the device is scheduled to restart.
        pending_tasks (int): The number of pending tasks for the device.
        n_qubits (int): The number of qubits of the device.
        n_nodes (int): The number of nodes of the device.
        basis_gates (str): The basis gates supported by the device.
        instructions (str): The supported instructions of the device.
        calibration_data (str): The calibration data of the device.
        calibrated_at (datetime): The date and time when the device was last calibrated.
        description (str): The description of the device.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    device_type: Mapped[enum.Enum] = mapped_column(
        Enum(
            "QPU",
            "simulator",
        ),
        nullable=False,
    )
    status: Mapped[enum.Enum] = mapped_column(
        Enum(
            "AVAILABLE",
            "NOT_AVAILABLE",
        ),
        nullable=False,
        default="NOT_AVAILABLE",
    )
    restart_at: Mapped[datetime.datetime] = mapped_column(
        nullable=True,
    )
    pending_tasks: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    n_qubits: Mapped[int] = mapped_column(
        nullable=False,
    )
    n_nodes: Mapped[int] = mapped_column(
        nullable=True,
    )
    basis_gates: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    instructions: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    calibration_data: Mapped[str]
    calibrated_at: Mapped[datetime.datetime]
    description: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
