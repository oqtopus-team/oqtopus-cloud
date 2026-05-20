import json
from datetime import datetime, timezone

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.user.routers.jobs import get_jobs
from oqtopus_cloud.worker.pending_jobs_updater.lambda_function import (
    update_pending_jobs,
)
from sqlalchemy import select

# Reference "now" used by the tests. Job submitted_at values and the `current`
# argument passed to update_pending_jobs are anchored to this so the
# COUNT_PENDING_JOBS_SINCE filter behaves deterministically regardless of when
# the test suite is executed.
FIXED_NOW = datetime(2024, 3, 12, 12, 34, 56, tzinfo=timezone.utc)


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


def _get_job(
    n: int,
    device_id: str,
    status: str,
    submitted_at: datetime | None = None,
) -> Job:
    if submitted_at is None:
        submitted_at = datetime(2024, 3, 3 + n, 12, 34, 56)
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": device_id,
        "job_type": "sampling",
        "job_info": json.dumps({"program": ["code"]}),
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": status,
        "shots": 1000,
        "submitted_at": submitted_at,
        "created_at": submitted_at,
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

    # call worker lambda with a fixed `current` so the COUNT_PENDING_JOBS_SINCE
    # filter window covers the fixed submitted_at values of the test jobs.
    update_pending_jobs(test_db, current=FIXED_NOW)

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
    update_pending_jobs(test_db, current=FIXED_NOW)
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


def test_count_pending_jobs_since_respects_env_var(test_db, monkeypatch):
    """COUNT_PENDING_JOBS_SINCE must control the cutoff applied to submitted_at.

    Two jobs are inserted:
      * job 1 submitted 1 day before FIXED_NOW
      * job 2 submitted 5 days before FIXED_NOW

    With COUNT_PENDING_JOBS_SINCE="2d" only the recent one falls inside the
    window, so device1.pending_jobs must become 1.
    With COUNT_PENDING_JOBS_SINCE="10d" both jobs fall inside the window, so
    device1.pending_jobs must become 2.
    """
    test_db.flush()
    test_db.add(_get_device("device1"))
    test_db.add(
        _get_job(
            1,
            "device1",
            "submitted",
            submitted_at=datetime(2024, 3, 11, 12, 34, 56),  # 1 day before FIXED_NOW
        )
    )
    test_db.add(
        _get_job(
            2,
            "device1",
            "submitted",
            submitted_at=datetime(2024, 3, 7, 12, 34, 56),  # 5 days before FIXED_NOW
        )
    )
    test_db.commit()

    # Narrow window: only the 1-day-old job should be counted.
    monkeypatch.setenv("COUNT_PENDING_JOBS_SINCE", "2d")
    update_pending_jobs(test_db, current=FIXED_NOW)
    assert (
        test_db.scalar(select(Device.pending_jobs).where(Device.id == "device1")) == 1
    )

    # Wide window: both jobs should be counted.
    monkeypatch.setenv("COUNT_PENDING_JOBS_SINCE", "10d")
    update_pending_jobs(test_db, current=FIXED_NOW)
    assert (
        test_db.scalar(select(Device.pending_jobs).where(Device.id == "device1")) == 2
    )


def test_count_pending_jobs_since_supports_hour_unit(test_db, monkeypatch):
    """The since string must accept non-day units such as hours."""
    test_db.flush()
    test_db.add(_get_device("device1"))
    test_db.add(
        _get_job(
            1,
            "device1",
            "submitted",
            submitted_at=datetime(2024, 3, 12, 10, 34, 56),  # 2 hours before FIXED_NOW
        )
    )
    test_db.add(
        _get_job(
            2,
            "device1",
            "submitted",
            submitted_at=datetime(2024, 3, 12, 6, 34, 56),  # 6 hours before FIXED_NOW
        )
    )
    test_db.commit()

    monkeypatch.setenv("COUNT_PENDING_JOBS_SINCE", "3h")
    update_pending_jobs(test_db, current=FIXED_NOW)
    assert (
        test_db.scalar(select(Device.pending_jobs).where(Device.id == "device1")) == 1
    )
