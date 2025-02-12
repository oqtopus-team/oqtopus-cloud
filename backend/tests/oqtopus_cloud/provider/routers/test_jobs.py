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
    jobtype_of_result,
    update_job_status,
)
from oqtopus_cloud.provider.schemas.jobs import (
    EstimationResult,
    GetJobsResponse,
    JobDef,
    JobInfo,
    JobResult,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    JobType,
    OperatorItem,
    UpdateJobInfo,
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


def _get_job_info(jt: JobType) -> JobInfo:
    return JobInfo(
        program=["code"],
        operator=[OperatorItem(pauli="X 0 Y 1 Z 2", coeff=[0.5, -2e-8])]
        if jt == JobType.estimation
        else None,
    )


def _get_job_model(n: int, jt: JobType) -> Job:
    mode_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "SC2",
        "job_type": jt.value,
        "job_info": JobInfo.model_dump_json(_get_job_info(jt)),
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
        "job_info": json.dumps({"program": ["code"]}),
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
        assert job.status == JobStatus.submitted

    jobs = get_jobs(device_id=device_id, db=test_db)
    assert isinstance(jobs, list)
    for job in jobs:
        assert job.device_id == device_id
        assert job.status != JobStatus.submitted

    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id
        assert job.status != JobStatus.submitted


def test_get_jobs_filtering(test_db: Session):
    # Arrange
    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.estimation))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC2&fields=job_id%2Cdescription%2Cjob_info")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob1id",
            description="test job 1",
            job_info=_get_job_info(JobType.sampling),
        ),
        GetJobsResponse(
            job_id="testjob2id",
            description="test job 2",
            job_info=_get_job_info(JobType.estimation),
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_timestamp(test_db: Session):
    # Arrange
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i, JobType.sampling))
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
        test_db.add(_get_job_model(i, JobType.sampling))
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

    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_device_model())
    test_db.commit()
    job_id = "testjob1id"
    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id
    test_db.add(_get_job_model(2, JobType.estimation))
    job_id = "testjob2id"
    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id


def test_update_job(test_db: Session):
    # Arrange
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.estimation))
    test_db.add(_get_device_model())
    test_db.commit()
    job_id1 = "testjob1id"
    request = JobStatusUpdate(status="running")
    actual = update_job_status(job_id=job_id1, request=request, db=test_db)

    expected = JobStatusUpdateResponse(message="Job status updated")
    # Assert
    assert actual == expected

    # for estimation jobs
    job_id2 = "testjob2id"
    actual2 = update_job_status(job_id=job_id2, request=request, db=test_db)
    assert actual2 == expected


def test_update_job_info_result(test_db: Session):
    cases: list[tuple[int, JobType, JobResult, int]] = [
        (
            1,
            JobType.sampling,
            JobResult(counts=json.dumps({"00": 1, "01": 2, "11": 3, "10": 4})),
            200,
        ),
        (
            2,
            JobType.estimation,
            JobResult(estimation=EstimationResult(exp_value=[1.0, 0.5], stds=0.0)),
            200,
        ),
        (
            3,
            JobType.sampling,
            JobResult(estimation=EstimationResult(exp_value=[1.0, 0.5], stds=0.0)),
            400,
        ),
        (
            4,
            JobType.estimation,
            JobResult(counts=json.dumps({"00": 1, "01": 2, "11": 3, "10": 4})),
            400,
        ),
    ]

    test_db.flush()
    test_db.add(_get_device_model())

    for n, jt, res, resp_expect in cases:
        job_model = _get_job_model(n, jt)
        bef_job_info = JobInfo.model_validate(json.loads(job_model.job_info))
        test_db.add(job_model)
        test_db.commit()

        # Submitting
        body = UpdateJobInfoRequest(job_info=UpdateJobInfo(result=res))
        submit_resp = client.patch(
            f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
        )
        assert submit_resp.status_code == resp_expect
        if resp_expect == 200:
            get_resp = client.get(f"/jobs/{job_model.id}")
            aft_job = JobDef.model_validate(get_resp.json())
            aft_job_info = aft_job.job_info
            assert bef_job_info.program == aft_job_info.program
            assert bef_job_info.operator == aft_job_info.operator
            assert aft_job_info.result == res
            assert aft_job_info.message is None
            assert aft_job.status == JobStatus.succeeded
            assert aft_job.job_type == jobtype_of_result(aft_job_info.result)


def test_update_job_info_reason(test_db: Session):
    job_model = _get_job_model(1, JobType.sampling)
    bef_job_info = JobInfo.model_validate(json.loads(job_model.job_info))
    test_db.add(_get_device_model())
    test_db.add(job_model)
    test_db.commit()

    # Submitting
    message = "Oops, job failed!"
    body = UpdateJobInfoRequest(
        overwrite_status=JobStatus.failed,
        job_info=UpdateJobInfo(message=message),
    )
    submit_resp = client.patch(
        f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
    )
    assert submit_resp.status_code == 200
    get_resp = client.get(f"/jobs/{job_model.id}")
    aft_job = JobDef.model_validate(get_resp.json())
    aft_job_info = aft_job.job_info
    assert bef_job_info.program == aft_job_info.program
    assert bef_job_info.operator == aft_job_info.operator
    assert aft_job_info.message == message
    assert aft_job_info.result is None
    assert aft_job.status == JobStatus.failed


def test_update_job_info_consist(test_db: Session):
    # None of the following updates should be acceptable.
    cases = [
        (
            1,
            JobType.sampling,
            JobResult(counts=json.dumps({"00": 1, "01": 2, "10": 3, "11": 4})),
            JobStatus.failed,
        ),
        (
            2,
            JobType.estimation,
            JobResult(estimation=EstimationResult(exp_value=[1.0, 0.0], stds=0.1)),
            JobStatus.failed,
        ),
        (4, JobType.sampling, None, JobStatus.submitted),
        (5, JobType.sampling, None, JobStatus.ready),
    ]

    test_db.add(_get_device_model())
    for n, jobtype, result, status in cases:
        job_model = _get_job_model(n, jobtype)
        job_info = JobInfo.model_validate(json.loads(job_model.job_info))
        if isinstance(result, str):
            job_info.message = result
        elif isinstance(result, JobResult):
            job_info.result = result
        job_model.job_info = job_info.model_dump_json()
        test_db.add(job_model)
        test_db.commit()

        resp = client.patch(
            f"jobs/{job_model.id}/job_info",
            content=UpdateJobInfoRequest(overwrite_status=status).model_dump_json(),
        )

        assert resp.status_code == 400


def test_update_job_status(test_db: Session):
    job_model = _get_job_model(1, JobType.sampling)
    test_db.add(_get_device_model())
    test_db.add(job_model)
    test_db.commit()

    resp = client.patch(
        f"/jobs/{job_model.id}/status",
        content=JobStatusUpdate(status="running").model_dump_json(),
    )
    assert resp.status_code == 200

    resp = client.patch(
        f"/jobs/{job_model.id}/status",
        content=JobStatusUpdate(status="running").model_dump_json(),
    )
    assert resp.status_code == 409


# TODO: add invalid test cases
# TODO: add test cases for handler
