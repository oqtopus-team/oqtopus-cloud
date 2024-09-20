import datetime
import enum
import uuid
from typing import Any, Literal

from sqlalchemy import JSON, TIMESTAMP, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import (
    VARBINARY,
)
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class Task(Base):
    """
    Represents a task in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (UUID): The unique identifier of the task.
        owner (str): The owner of the task.
        name (str): The name of the task.
        device (str): The device used for the task.
        n_qubits (int): The number of qubits used in the task.
        n_nodes (int): The number of nodes used in the task.
        code (str): The code associated with the task.
        action (str): The action to be performed by the task (sampling or estimation).
        method (str): The method used for the task (state_vector or sampling).
        shots (int): The number of shots for the task.
        operator (str): The operator used in the task.
        qubit_allocation (str): The qubit allocation for the task.
        skip_transpilation (bool): Flag indicating whether transpilation should be skipped.
        seed_transpilation (int): The seed used for transpilation.
        seed_simulation (int): The seed used for simulation.
        n_per_node (int): The number of tasks per node.
        simulation_opt (str): The simulation optimization used for the task.
        ro_error_mitigation (str): The error mitigation method used for readout errors.
        note (str): Additional notes for the task.
        status (str): The status of the task (QUEUED, QUEUED_FETCHED, RUNNING, COMPLETED, FAILED, CANCELLING, CANCELLING_FETCHED, CANCELLED).
        created_at (datetime): The timestamp when the task was created.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        VARBINARY(16),
        primary_key=True,
    )
    owner: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=True)
    device: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("devices.id"),
        nullable=False,
    )
    n_qubits: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    n_nodes: Mapped[int] = mapped_column(
        nullable=True,
    )
    code: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    action: Mapped[enum.Enum] = mapped_column(
        Enum(
            "sampling",
            "estimation",
        ),
        nullable=False,
    )
    method: Mapped[enum.Enum] = mapped_column(
        Enum(
            "state_vector",
            "sampling",
        ),
        nullable=True,
    )
    shots: Mapped[int] = mapped_column(
        nullable=True,
    )
    operator: Mapped[str] = mapped_column(
        String(1024),
        nullable=True,
    )
    qubit_allocation: Mapped[dict[str, int]] = mapped_column(JSON)
    skip_transpilation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    seed_transpilation: Mapped[int] = mapped_column(nullable=True)
    seed_simulation: Mapped[int] = mapped_column(nullable=True)
    n_per_node: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )
    simulation_opt: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    ro_error_mitigation: Mapped[
        Literal[
            "none",
            "pseudo_inverse",
            "least_square",
        ]
    ] = mapped_column(
        Enum(
            "none",
            "pseudo_inverse",
            "least_square",
        ),
        nullable=True,
    )
    note: Mapped[str] = mapped_column(String(1024), nullable=True)
    status: Mapped[enum.Enum] = mapped_column(
        Enum(
            "QUEUED",
            "QUEUED_FETCHED",
            "RUNNING",
            "COMPLETED",
            "FAILED",
            "CANCELLING",
            "CANCELLING_FETCHED",
            "CANCELLED",
        ),
        nullable=False,
        default="QUEUED",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        default="CURRENT_TIMESTAMP",
    )


class Error(Exception):
    pass


class TaskNotFound(Error):
    """Exception raised when a task is not found.

    Args:
        Error (type): The base error class.

    """

    pass
