import datetime
import enum

from sqlalchemy import (
    Enum,
    String,
    TIMESTAMP
)
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class Job(Base):
    """
    Represents a job in the system.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        id (str): The unique identifier of the job.
        owner (str): The owner of the job.
        name (str): The name of the job.
        description (str): Additional notes for the job.
        device_id (str): The device used for the job.
        n_qubits (int): The number of qubits used in the job.
        job_detail(str): The details of the job.
        transpiler_info(str): The information about the transpiler.
        simulator_info(str): The information about the simulator.
        mitigation_info(str): The information about the error mitigation.
        job_type (str): The action to be performed by the job (sampling or estimation).
        shots (int): The number of shots for the job.
        status (str): The status of the job (submitted, ready, running, success, failed, cancelled).
        created_at (datetime): The timestamp when the job was created.
        updated_at(datetime): The timestamp when the job was last updated.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    owner: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    device_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    job_detail: Mapped[str]
    transpiler_info: Mapped[str]
    simulator_info: Mapped[str]
    mitigation_info: Mapped[str]
    job_type: Mapped[enum.Enum] = mapped_column(
        Enum(
            "sampling",
            "estimation",
            "sse",
        ),
        nullable=False,
    )
    shots: Mapped[int] = mapped_column(
        nullable=True,
    )
    status: Mapped[enum.Enum] = mapped_column(
        Enum(
            "submitted",
            "ready",
            "running",
            "success",
            "failed",
            "cancelled",
        ),
        nullable=False,
        default="submitted",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        default="CURRENT_TIMESTAMP",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP,
        default="CURRENT_TIMESTAMP",
    )


class Error(Exception):
    pass


class JobNotFound(Error):
    """Exception raised when a job is not found.

    Args:
        Error (type): The base error class.

    """

    pass
