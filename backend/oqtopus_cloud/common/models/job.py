import datetime
from typing import Literal, Optional

from sqlalchemy import TIMESTAMP, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.device import DeviceId

JobId = str

JobType = Literal["sampling", "estimation", "sse", "multi_manual"]

JobStatus = Literal["submitted", "ready", "running", "succeeded", "failed", "cancelled"]


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
        job_info(str): The information of the job.
        transpiler_info(str): The information about the transpiler.
        simulator_info(str): The information about the simulator.
        mitigation_info(str): The information about the error mitigation.
        job_type (str): The action to be performed by the job (sampling or estimation).
        shots (int): The number of shots for the job.
        status (str): The status of the job (submitted, ready, running, succeeded, failed, cancelled).
        execution_time(float): The duration of the QPU execution.
        submitted_at(datetime): The timestamp when the job was submitted.
        ready_at(datetime): The timestamp when the job became ready.
        running_at(datetime): The timestamp when the job started running.
        ended_at(datetime): The timestamp when the job ended.
        created_at (datetime): The timestamp when the job was created.
        updated_at(datetime): The timestamp when the job was last updated.
    """

    __tablename__ = "jobs"

    id: Mapped[JobId] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(String(1024), nullable=True)
    job_type: Mapped[JobType] = mapped_column(String(32), nullable=False)
    device_id: Mapped[DeviceId] = mapped_column(String(64), nullable=False)
    shots: Mapped[int] = mapped_column(nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        String(32), nullable=False, default="submitted"
    )
    job_info: Mapped[str] = mapped_column(Text)
    transpiler_info: Mapped[str] = mapped_column(Text)
    simulator_info: Mapped[str] = mapped_column(Text)
    mitigation_info: Mapped[str] = mapped_column(Text)
    execution_time: Mapped[float] = mapped_column(Float, nullable=True)
    submitted_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=True)
    ready_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=True)
    running_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=True)
    ended_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP, nullable=False, server_default=func.CURRENT_TIMESTAMP()
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_onupdate=func.current_timestamp(),
    )


class Error(Exception):
    pass


class JobNotFound(Error):
    """Exception raised when a job is not found.

    Args:
        Error (type): The base error class.

    """

    pass
