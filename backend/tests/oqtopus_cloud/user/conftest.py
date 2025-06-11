import os
from datetime import datetime
from typing import (
    Generator,
)

import pytest
import pytz
from oqtopus_cloud.common.models.base import (
    Base,
)
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, FSSpecStorage
from oqtopus_cloud.user.lambda_function import app
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
            status="available",
            available_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            pending_jobs=2,
            n_qubits=64,
            basis_gates='["sx", "rx", "rzx90", "id"]',
            instructions='["measure", "barrier"]',
            device_info="{}",
            calibrated_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            description="Superconducting quantum computer",
            created_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
        ),
        # Job(
        #     id="7af020f6-2e38-4d70-8cf0-4349650ea08c",
        #     owner="admin",
        #     name="Bell State Sampling Example",
        #     description="An example of Bell state sampling job",
        #     device_id="Kawasaki",
        #     job_type="sampling",
        #     job_info=json.dumps(
        #         {
        #             "desc": {
        #                 "job_type": "sampling",
        #                 "code": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
        #             },
        #             "result": None,
        #             "transpiled_code": None,
        #             "reason": None,
        #         }
        #     ),
        #     simulator_info=json.dumps(
        #         {
        #             "n_qubits": 5,
        #             "n_nodes": 12,
        #             "n_per_node": 2,
        #             "seed_simulation": 39058567,
        #             "simulation_opt": {
        #                 "optimization_method": "light",
        #                 "optimization_block_size": 1,
        #                 "optimization_swap_level": 1,
        #             },
        #         }
        #     ),
        #     transpiler_info="",
        #     mitigation_info="",
        #     shots=1000,
        #     status="submitted",
        #     created_at=datetime(2024, 3, 4, 12, 34, 56),
        # ),
        # Job(
        #     id="01927422-86d4-7cbf-98d3-32f5f1263cd9",
        #     owner="admin",
        #     name="Bell State Estimation Example",
        #     description="An example of Bell state estimation job",
        #     device_id="Kawasaki",
        #     job_type="estimation",
        #     job_info=json.dumps(
        #         {
        #             "desc": {
        #                 "job_type": "estimation",
        #                 "code": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
        #                 "operator": "X 0 X 1",
        #             },
        #             "result": None,
        #             "transpiled_code": None,
        #             "reason": None,
        #         }
        #     ),
        #     simulator_info=json.dumps(
        #         {
        #             "n_qubits": 5,
        #             "n_nodes": 12,
        #             "n_per_node": 2,
        #             "seed_simulation": 39058567,
        #             "simulation_opt": {
        #                 "optimization_method": "light",
        #                 "optimization_block_size": 1,
        #                 "optimization_swap_level": 1,
        #             },
        #         }
        #     ),
        #     transpiler_info="",
        #     mitigation_info="",
        #     shots=1000,
        #     status="submitted",
        #     created_at=datetime(2024, 3, 4, 12, 34, 56),
        # ),
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


@pytest.fixture(scope="function")
def test_storage(fake_os_env) -> Generator[FSSpecStorage, None, None]:
    # tmp_path 配下に "storage" ディレクトリを作ることで環境変数と整合性を持たせる
    local_storage_path = os.environ["STORAGE_LOCAL_BASE_PATH"]
    os.mkdir(local_storage_path)
    yield FSSpecStorage(fs_url=f"file://{local_storage_path}")


@pytest.fixture(autouse=True)
def fake_os_env(monkeypatch, tmp_path):
    monkeypatch.setenv("STORAGE_DRIVER", "local")
    monkeypatch.setenv("STORAGE_LOCAL_BASE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("SSE_BUCKET", "oqtopus_test_bucket")
    monkeypatch.setenv("SSE_USER_PROGRAM_NAME", "oqtopus_test_program.py")
    monkeypatch.setenv("SSE_CONTAINER_LOG_NAME", "qtopus_test_sse_log.log")
    monkeypatch.setenv("SSE_ZIP_FILE_NAME", "oqtopus_test_sse_log_{job_id}.zip")
