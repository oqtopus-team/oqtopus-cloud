import datetime
import decimal
from typing import Optional

from sqlalchemy import Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.common import TimestampMixin


class Job(Base, TimestampMixin):
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
        transpiler_info(str): The information about the transpiler.
        simulator_info(str): The information about the simulator.
        mitigation_info(str): The information about the error mitigation.
        job_type (str): The action to be performed by the job (sampling or estimation).
        shots (int): The number of shots for the job.
        status (str): The status of the job (registered, submitted, ready, running, succeeded, failed, cancelled).
        output_files (str): List of job output files uploaded by provider.
        message (str): Message set by provider.
        execution_time(float): The duration of the QPU execution.
        submitted_at(datetime): The timestamp when the job was submitted.
        ready_at(datetime): The timestamp when the job became ready.
        running_at(datetime): The timestamp when the job started running.
        ended_at(datetime): The timestamp when the job ended.
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
    name: Mapped[str] = mapped_column(String(256), nullable=False, server_default="")
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    device_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    # NOT NULL even though init/01.schema.sql allows NULL: API handlers
    # substitute "{}" for missing values before insert (see Lambda handlers).
    transpiler_info: Mapped[str] = mapped_column(Text, nullable=False)
    simulator_info: Mapped[str] = mapped_column(Text, nullable=False)
    mitigation_info: Mapped[str] = mapped_column(Text, nullable=False)
    job_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="sampling",
        server_default="sampling",
    )
    shots: Mapped[int] = mapped_column(
        nullable=False,
        default=1000,
        server_default=text("1000"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="submitted",
        server_default="submitted",
    )
    execution_time: Mapped[decimal.Decimal] = mapped_column(
        Numeric(65, 3),
        nullable=True,
    )
    output_files: Mapped[Optional[str]]
    message: Mapped[Optional[str]]
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTimeTz(), nullable=True)
    ready_at: Mapped[datetime.datetime] = mapped_column(DateTimeTz(), nullable=True)
    running_at: Mapped[datetime.datetime] = mapped_column(DateTimeTz(), nullable=True)
    ended_at: Mapped[datetime.datetime] = mapped_column(DateTimeTz(), nullable=True)


class Error(Exception):
    pass


class JobNotFound(Error):
    """Exception raised when a job is not found.

    Args:
        Error (type): The base error class.

    """

    pass
