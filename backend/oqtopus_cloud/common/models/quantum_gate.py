from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from oqtopus_cloud.common.models import Base

GateId = str


class QuantumGate(Base):
    __tablename__ = "quantum_gates"

    id: Mapped[str] = mapped_column(String(16), nullable=False, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    n_qubits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    n_clbits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
