import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from oqtopus_cloud.common.model_util import StringEnumType
from oqtopus_cloud.common.models import Base
from oqtopus_cloud.common.models.quantum_gate import QuantumGate

DeviceId = str

devices_gates_support = Table(
    "gate_supports",
    Base.metadata,
    Column("device_id", ForeignKey("devices.id"), primary_key=True),
    Column("gate_id", ForeignKey("quantum_gates.id"), primary_key=True),
)


class DeviceType(Enum):
    QPU = "qpu"
    Simulator = "simulator"


class Device(Base):
    """
    Represents a device in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (str): The unique identifier of the device.
        device_type (DeviceType): The type of the device (QPU or simulator).
        availability (bool): The availability of the device (true = AVAILABLE, false = NOT_AVAILABLE).
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
    device_type: Mapped[DeviceType] = mapped_column(
        StringEnumType(DeviceType),
        nullable=False,
    )
    availability: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
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

    basis_gates: Mapped[list[QuantumGate]] = relationship(
        secondary=devices_gates_support
    )
    instructions: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    calibration_data: Mapped[str] = mapped_column(Text, nullable=True)
    calibrated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    description: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
