import os
import uuid
from datetime import datetime
from typing import (
    Generator,
)

import pytest
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.task import (
    Task,
)
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.provider.lambda_function import app
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)
from sqlalchemy.orm.session import (
    close_all_sessions,
)


class TestingSession(Session):
    """_summary_

    Args:
            Session (_type_): _description_
    """

    def commit(
        self,
    ) -> None:
        self.flush()
        self.expire_all()


def insert_initial_data(db: Session):
    initial_data = [
        Device(
            id="Kawasaki",
            device_type="QPU",
            status="NOT_AVAILABLE",
            restart_at=datetime(2024, 3, 4, 12, 34, 56),
            pending_tasks=0,
            n_qubits=64,
            n_nodes=0,
            basis_gates='["sx", "rx", "rzx90", "id"]',
            instructions='["measure", "barrier"]',
            calibration_data="{}",
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56),
            description="Superconducting quantum computer",
        ),
        Task(
            id=uuid.UUID("7af020f6-2e38-4d70-8cf0-4349650ea08c").bytes,
            owner="admin",
            name="Test task 1",
            device="Kawasaki",
            code='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
            n_qubits=2,
            n_nodes=12,
            action="sampling",
            method="state_vector",
            shots=1024,
            operator="Z0*Z1",
            qubit_allocation=None,
            skip_transpilation=0,
            seed_transpilation=None,
            seed_simulation=None,
            n_per_node=1,
            simulation_opt=None,
            ro_error_mitigation="none",
            note=None,
            status="COMPLETED",
            created_at=datetime(2024, 3, 4, 12, 34, 56),
        ),
        Task(
            id=uuid.UUID("7af020f6-2e38-4d70-8cf0-4349650ea08d").bytes,
            owner="admin",
            name="Test task 2",
            device="Kawasaki",
            code='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
            n_qubits=2,
            n_nodes=12,
            action="sampling",
            method="state_vector",
            shots=1024,
            operator="Z0*Z1",
            qubit_allocation=None,
            skip_transpilation=0,
            seed_transpilation=None,
            seed_simulation=None,
            n_per_node=1,
            simulation_opt=None,
            ro_error_mitigation="none",
            note=None,
            status="QUEUED_FETCHED",
            created_at=datetime(2024, 3, 4, 12, 34, 56),
        ),
    ]
    db.add_all(initial_data)
    db.commit()


@pytest.fixture(scope="function")
def test_db() -> (
    Generator[
        Session,
        None,
        None,
    ]
):
    """_summary_

    Yields:
            Generator[Session, None, None]: _description_
    """
    print("SetUp")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=True,
    )
    # Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(
        class_=TestingSession,
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestSessionLocal()

    # https://fastapi.tiangolo.com/advanced/testing-dependencies/
    def get_db_for_testing() -> (
        Generator[
            Session,
            None,
            None,
        ]
    ):
        try:
            yield db
            db.commit()
        except SQLAlchemyError as e:
            assert e is not None
            db.rollback()

    app.dependency_overrides[get_db] = get_db_for_testing
    insert_initial_data(db)

    yield db

    os.remove("./test.db")
    db.rollback()
    close_all_sessions()
    engine.dispose()
