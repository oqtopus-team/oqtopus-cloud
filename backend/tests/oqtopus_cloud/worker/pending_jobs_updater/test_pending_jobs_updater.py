import json
from datetime import datetime

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.user.routers.jobs import get_jobs
from oqtopus_cloud.worker.pending_jobs_updater.lambda_function import (
    update_pending_jobs,
)
from sqlalchemy import select


def _get_device(id: str) -> Device:
    mode_dict = {
        "id": id,
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "device_info": "{}",
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Device(**mode_dict)


def _get_job(n: int, device_id: str, status: str) -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": device_id,
        "job_type": "sampling",
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": status,
        "shots": 1000,
        "submitted_at": datetime(2024, 3, 3 + n, 12, 34, 56),
        "created_at": datetime(2024, 3, 3 + n, 12, 34, 56),
    }
    return Job(**model_dict)


def test_update_pending_jobs(
    test_db,
):
    """_summary_
    Update pending jobs
    """

    # initialization
    test_db.flush()
    test_db.add(_get_device("device1"))
    test_db.add(_get_device("device2"))
    test_db.add(_get_job(1, "device1", "submitted"))
    test_db.add(_get_job(2, "device2", "submitted"))
    test_db.add(_get_job(3, "device2", "submitted"))
    test_db.add(_get_job(4, "device2", "ready"))
    test_db.add(_get_job(5, "device2", "running"))
    test_db.add(_get_job(6, "device1", "succeeded"))
    test_db.commit()

    # call worker lambda
    update_pending_jobs(test_db)

    # get pending_jobs from DB
    device1_pending_jobs = test_db.scalar(
        select(Device.pending_jobs).where(Device.id == "device1")
    )
    device2_pending_jobs = test_db.scalar(
        select(Device.pending_jobs).where(Device.id == "device2")
    )

    # assertion
    assert device1_pending_jobs == 1
    assert device2_pending_jobs == 4

    test_db.add(_get_job(7, "device1", "running"))
    test_db.add(_get_job(8, "device2", "submitted"))
    test_db.commit()

    # call worker lambda
    update_pending_jobs(test_db)
    # get pending_jobs from DB
    device1_pending_jobs = test_db.scalar(
        select(Device.pending_jobs).where(Device.id == "device1")
    )
    device2_pending_jobs = test_db.scalar(
        select(Device.pending_jobs).where(Device.id == "device2")
    )

    # assertion
    assert device1_pending_jobs == 2
    assert device2_pending_jobs == 5
