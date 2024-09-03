import enum
import uuid

from sqlalchemy import (
    Enum,
    ForeignKey,
)
from sqlalchemy.dialects.mysql import (
    VARBINARY,
)
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models.base import (
    Base,
)


class Result(Base):
    """
    Represents the result of a task execution.

    See https://github.com/sqlalchemy/sqlalchemy/issues/5613 for the reason why we need to use nullable=True for some columns.

    Attributes:
        task_id (bytes): The ID of the task associated with this result.
        status (str): The status of the result (SUCCESS, FAILURE, CANCELLED).
        result (str): The result of the task execution.
        reason (str): The reason for the result (if any).
        transpiled_code (str): The transpiled code generated during execution.
        qubit_allocation (str): The allocation of qubits used during execution.
    """

    __tablename__ = "results"

    task_id: Mapped[uuid.UUID] = mapped_column(
        VARBINARY(16),
        ForeignKey(
            "tasks.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    status: Mapped[enum.Enum] = mapped_column(
        Enum(
            "SUCCESS",
            "FAILURE",
            "CANCELLED",
        ),
        nullable=False,
    )
    result: Mapped[str] = mapped_column(
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(
        nullable=True,
    )
    transpiled_code: Mapped[str]
    qubit_allocation: Mapped[str] = mapped_column(
        nullable=True,
    )
