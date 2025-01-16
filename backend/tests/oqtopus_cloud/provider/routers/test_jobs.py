import json
from datetime import datetime
from typing import List

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.job import (
    Job,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.routers.jobs import (
    get_job,
    get_jobs,
    update_job,
)
from oqtopus_cloud.provider.schemas.jobs import (
    GetJobsResponse,
    JobDef,
    JobInfo,
    JobInfoSampling,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    UpdateJobInfoRequest,
)
from pydantic.type_adapter import TypeAdapter
from sqlalchemy.orm.session import Session
from zoneinfo import ZoneInfo

# sqlite does not support jst timezone
# utc = ZoneInfo("UTC")
utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

client = TestClient(app)

# def _get_calibration_dict() -> Dict:
#     calib_dict = {
#         "qubitConnectivity": ["(1,4)", "(4,5)", "(5,8)"],
#         "t1": {"0": 55.51, "1": 37.03, "2": 57.13},
#         "t2": {"0": 99.31, "1": 111.03, "2": 30.12},
#         "roError": {"0": 4.67e-2, "1": 1.8e-1, "2": 3.55e-1},
#         "gateError": {"sx": {"0": 6.92e-3, "1": 2.96e-3, "2": 7.2e-2}},
#         "measProb0As1": {"0": 6.08e-3, "1": 1.2e-2, "2": 2.48e-1},
#         "measProb1As0": {"0": 2.81e-2, "1": 3.86e-1, "2": 8.11e-2},
#         "gateDuration": {"sx": {"0": 29.3, "1": 50.9, "2": 45.4}},
#     }
#     return calib_dict


def _get_device_model():
    mode_dict = {
        "id": "SC2",
        "device_type": "QPU",
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


def _get_job_model(n: int) -> Job:
    mode_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "SC2",
        "job_type": "sampling",
        "job_info": json.dumps(
            {
                "desc": {
                    "job_type": "sampling",
                    "code": "code",
                }
            }
        ),
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": "ready",
        "shots": 1000,
        "submitted_at": datetime(2024, 3, 4 + n, 12, 34, 56),
        "created_at": datetime(2024, 3, 4 + n, 12, 34, 56),
    }
    return Job(**mode_dict)


def _get_job_model_2() -> Job:
    mode_dict = {
        "id": "testjob2id",
        "owner": "admin",
        "name": "testjob2",
        "description": "test job 2",
        "device_id": "SC2",
        "job_type": "sampling",
        "job_info": json.dumps(
            {
                "desc": {
                    "job_type": "sampling",
                    "code": "code",
                }
            }
        ),
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": "submitted",
        "shots": 1000,
        "submitted_at": datetime(2024, 3, 4, 12, 34, 56),
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Job(**mode_dict)


def test_get_jobs(test_db: Session):
    # Arrange
    test_db.flush()
    test_db.add(_get_job_model_2())
    test_db.add(_get_device_model())
    test_db.commit()
    device_id = "SC2"
    job_id = "testjob2id"

    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.status == "submitted"

    jobs = get_jobs(device_id=device_id, db=test_db)
    assert jobs[0].device_id == device_id
    assert jobs[0].status == "ready"

    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.status == "ready"


def test_get_jobs_filtering(test_db: Session):
    # Arrange
    test_db.flush()
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC2&fields=job_id%2Cdescription%2Cjob_info")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob1id",
            description="test job 1",
            job_info=JobInfo(
                desc=JobInfoSampling(job_type="sampling", code="code"),
            ),
        ),
        GetJobsResponse(
            job_id="testjob2id",
            description="test job 2",
            job_info=JobInfo(
                desc=JobInfoSampling(job_type="sampling", code="code"),
            ),
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_timestamp(test_db: Session):
    # Arrange
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get(
        "/jobs?device_id=SC2&fields=job_id&timestamp=2024-03-11T07%3A04%3A24%2B09%3A00"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob7id",
        ),
        GetJobsResponse(
            job_id="testjob8id",
        ),
        GetJobsResponse(
            job_id="testjob9id",
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_max_results(test_db: Session):
    # Arrange
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC2&fields=job_id&max_results=3")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob1id",
        ),
        GetJobsResponse(
            job_id="testjob2id",
        ),
        GetJobsResponse(
            job_id="testjob3id",
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_job(test_db: Session):
    # Arrange

    test_db.add(_get_job_model(1))
    test_db.add(_get_device_model())
    test_db.commit()
    job_id = "testjob1id"
    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id


def test_update_job(test_db: Session):
    # Arrange
    test_db.add(_get_job_model(1))
    test_db.add(_get_device_model())
    test_db.commit()
    job_id = "testjob1id"
    request = JobStatusUpdate(status="running")
    actual = update_job(job_id=job_id, request=request, db=test_db)

    expected = JobStatusUpdateResponse(message="Job status updated")
    # Assert

    assert actual == expected


def test_update_job_info_400(test_db: Session):
    job_model = _get_job_model(1)
    test_db.add(_get_device_model())
    test_db.add(job_model)
    test_db.commit()

    # Submitting
    result = json.dumps({"field1": "value", "field2": "value2"})
    reason = "Oops! Job failed!"
    body = UpdateJobInfoRequest(
        result=result,
        reason=reason,
    )
    submit_resp = client.patch(
        f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
    )
    assert submit_resp.status_code == 400


def test_update_job_info_result(test_db: Session):
    job_model = _get_job_model(1)
    bef_job_info = JobInfo.model_validate(json.loads(job_model.job_info))
    test_db.add(_get_device_model())
    test_db.add(job_model)
    test_db.commit()

    # Submitting
    result = json.dumps({"field1": "value", "field2": "value2"})
    transpiled_code = "transpiled_code"
    body = UpdateJobInfoRequest(
        result=result,
        transpiled_code=transpiled_code,
    )
    submit_resp = client.patch(
        f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
    )
    assert submit_resp.status_code == 200
    get_resp = client.get(f"/jobs/{job_model.id}")
    aft_job = JobDef.model_validate(get_resp.json())
    aft_job_info = aft_job.job_info
    assert bef_job_info.desc == aft_job_info.desc
    assert aft_job_info.result == result
    assert aft_job_info.reason is None
    assert aft_job.status == JobStatus.succeeded


def test_update_job_info_reason(test_db: Session):
    job_model = _get_job_model(1)
    bef_job_info = JobInfo.model_validate(json.loads(job_model.job_info))
    test_db.add(_get_device_model())
    test_db.add(job_model)
    test_db.commit()

    # Submitting
    reason = "Oops, job failed!"
    body = UpdateJobInfoRequest(
        reason=reason,
    )
    submit_resp = client.patch(
        f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
    )
    assert submit_resp.status_code == 200
    get_resp = client.get(f"/jobs/{job_model.id}")
    aft_job = JobDef.model_validate(get_resp.json())
    aft_job_info = aft_job.job_info
    assert bef_job_info.desc == aft_job_info.desc
    assert aft_job_info.reason == reason
    assert aft_job_info.result is None
    assert aft_job.status == JobStatus.failed


# TODO: add invalid test cases
# TODO: add test cases for handler
