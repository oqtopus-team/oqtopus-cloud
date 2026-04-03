import base64
import json
import os
from datetime import datetime
from typing import List

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.job import (
    Job as JobModel,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.routers.jobs import (
    get_job,
    get_jobs,
    jobtype_of_result,
    update_job_status,
)
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
)
from oqtopus_cloud.provider.schemas.jobs import (
    EstimationResult,
    Job,
    JobDef,
    JobInfo,
    JobResult,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    JobType,
    OperatorItem,
    SamplingResult,
    TranspileResult,
    UpdateJobInfo,
    UpdateJobInfoRequest,
    UpdateJobTranspilerInfoRequest,
    UploadSselogResponse,
)
from pydantic.type_adapter import TypeAdapter
from sqlalchemy.orm.session import Session
from zoneinfo import ZoneInfo

# sqlite does not support jst timezone
utc = ZoneInfo("UTC")

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
        operator=[OperatorItem(pauli="X 0 Y 1 Z 2", coeff=0.5)]
        if jt == JobType.estimation
        else None,
    )


def _get_job_model(n: int, jt: JobType) -> JobModel:
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
    return JobModel(**mode_dict)


def _get_job_model_2() -> JobModel:
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
    return JobModel(**mode_dict)


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


def test_get_jobs_ignore_illegal_job(
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.sampling))
    # job3 has invalid job_info
    job_3 = _get_job_model(3, JobType.sampling)
    job_3.job_info = json.dumps({"dummy": ["dummy"]})
    test_db.add(job_3)
    test_db.commit()

    response = client.get("/jobs?device_id=SC2")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert len(actual) == 2
    assert actual[0].job_id == "testjob1id"
    assert actual[1].job_id == "testjob2id"


def test_get_jobs_filtering_fields(
    test_db,
):
    """_summary_
    GET /jobs with filtering test
    """

    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.sampling))
    test_db.commit()

    response = client.get(
        "/jobs?device_id=SC2&fields=job_id,name,job_type,status,job_info,transpiler_info"
    )
    adapter = TypeAdapter(List[Job])
    actual = adapter.validate_python(response.json())

    expect = [
        Job(
            job_id="testjob1id",
            name="testjob1",
            job_type=JobType.sampling,
            status=JobStatus.ready,
            job_info=JobInfo(program=["code"]),
            transpiler_info={"this_is": "transpiler_info"},
        ),
        Job(
            job_id="testjob2id",
            name="testjob2",
            job_type=JobType.sampling,
            status=JobStatus.ready,
            job_info=JobInfo(program=["code"]),
            transpiler_info={"this_is": "transpiler_info"},
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_all_fields(test_db):
    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.sampling))
    test_db.commit()

    # This is the request sent from oqtopus-frontend
    response = client.get(
        "jobs?device_id=SC2&fields=job_id,name,description,device_id,job_info,transpiler_info,simulator_info,mitigation_info,job_type,shots,status"
    )
    adapter = TypeAdapter(List[Job])
    actual = adapter.validate_python(response.json())
    assert response.status_code == 200
    assert len(actual) == 2


def test_get_jobs_invalid_fields(
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.sampling))
    test_db.commit()

    response = client.get("/jobs?device_id=SC2&fields=XXX,status,YYY")
    actual = response.json()
    expect = json.loads(
        BadRequestResponse(
            message=f"fields {["XXX", "YYY"]} is invalid"
        ).body.decode()
    )

    assert response.status_code == 400
    assert actual == expect


def test_get_jobs_timestamp(test_db: Session):
    # Arrange
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i, JobType.sampling))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get(
        "/jobs?device_id=SC2&timestamp=2024-03-11T07%3A04%3A24Z"
    )
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())
    assert isinstance(actual, list) and len(actual) == 3
    expect = [
        "testjob7id",
        "testjob8id",
        "testjob9id",
    ]

    assert response.status_code == 200
    for act, exp_job_id in zip(actual, expect):
        assert act.job_id == exp_job_id


def test_get_jobs_limit(test_db: Session):
    # Arrange
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i, JobType.sampling))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC2&limit=3")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())
    expect_job_ids = [
        "testjob1id",
        "testjob2id",
        "testjob3id",
    ]

    assert response.status_code == 200
    for act, exp_job_id in zip(actual, expect_job_ids):
        assert act.job_id == exp_job_id


def test_get_job(test_db: Session):
    # Arrange

    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_device_model())
    test_db.commit()
    job_id = "testjob1id"
    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id
        assert job.status == JobStatus.ready
    test_db.add(_get_job_model(2, JobType.estimation))
    job_id = "testjob2id"
    job = get_job(job_id=job_id, db=test_db)
    if isinstance(job, JobDef):
        assert job.job_id == job_id
        assert job.status == JobStatus.ready


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
    cases: list[tuple[int, JobType, JobResult, float, int]] = [
        (
            1,
            JobType.sampling,
            JobResult(sampling=SamplingResult(counts={"00": 1, "11": 2})),
            123.45,
            200,
        ),
        (
            2,
            JobType.estimation,
            JobResult(estimation=EstimationResult(exp_value=1.0, stds=0.0)),
            45.6,
            200,
        ),
        (
            3,
            JobType.sampling,
            JobResult(estimation=EstimationResult(exp_value=1.0, stds=0.0)),
            7.89,
            400,
        ),
        (
            4,
            JobType.estimation,
            JobResult(sampling=SamplingResult(counts={"00": 1, "11": 2})),
            10,
            400,
        ),
    ]

    test_db.flush()
    test_db.add(_get_device_model())

    for n, jt, res, exectime, resp_expect in cases:
        job_model = _get_job_model(n, jt)
        bef_job_info = JobInfo.model_validate(json.loads(job_model.job_info))
        test_db.add(job_model)
        test_db.commit()

        # Submitting
        body = UpdateJobInfoRequest(
            job_info=UpdateJobInfo(result=res), execution_time=exectime
        )
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
            assert aft_job.execution_time == exectime
            assert aft_job.ended_at is not None
            assert aft_job.job_type in jobtype_of_result(aft_job_info.result)


def test_update_job_info_transpile_result(test_db: Session):
    job_model = _get_job_model(1, JobType.sampling)
    test_db.add(_get_device_model())
    # Set ready
    job_model.ready_at = datetime.now(utc)
    job_model.status = JobStatus.ready
    test_db.add(job_model)
    test_db.commit()

    # Submitting
    transpile_result = TranspileResult(
        transpiled_program="transpiled_program",
        stats={"field": "value"},
        virtual_physical_mapping={"field": "value"},
    )
    body = UpdateJobInfoRequest(
        overwrite_status=JobStatus.ready,
        job_info=UpdateJobInfo(transpile_result=transpile_result),
    )
    submit_resp = client.patch(
        f"/jobs/{job_model.id}/job_info", content=body.model_dump_json()
    )
    assert submit_resp.status_code == 200
    get_resp = client.get(f"/jobs/{job_model.id}")
    aft_job = JobDef.model_validate(get_resp.json())
    aft_job_info = aft_job.job_info
    assert aft_job_info.transpile_result == aft_job_info.transpile_result
    assert aft_job_info.message is None
    assert aft_job_info.result is None
    assert aft_job.status == JobStatus.ready


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
    assert aft_job.ended_at is not None


def test_update_job_info_consist(test_db: Session):
    # None of the following updates should be acceptable.
    cases = [
        (
            1,
            JobType.sampling,
            JobResult(sampling=SamplingResult(counts={"00": 1, "11": 2})),
            JobStatus.failed,
        ),
        (
            2,
            JobType.estimation,
            JobResult(estimation=EstimationResult(exp_value=1.0, stds=0.1)),
            JobStatus.failed,
        ),
        (4, JobType.sampling, None, JobStatus.submitted),
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
    model = test_db.get(JobModel, job_model.id)
    assert model is not None
    assert model.status == JobStatus.running
    assert model.running_at is not None
    running_at = model.running_at
    assert resp.status_code == 200

    resp = client.patch(
        f"/jobs/{job_model.id}/status",
        content=JobStatusUpdate(status="running").model_dump_json(),
    )
    assert model.status == JobStatus.running
    assert running_at == running_at
    assert resp.status_code == 409


# TODO: add invalid test cases
# TODO: add test cases for handler


def test_get_ssesrc(test_storage):
    # Arrange
    program_name = os.environ["SSE_USER_PROGRAM_NAME"]
    job_id = "testjob1id"
    src_body = "program1"
    test_storage.put(key=f"{job_id}/{program_name}", data=b"program1")

    resp = client.get(f"/jobs/{job_id}/ssesrc")
    resp.status_code == 200
    decoded = base64.b64decode(resp.content).decode("utf-8")
    assert decoded == src_body


def test_get_ssesrc_no_src():
    # Arrange skip creating object for this test
    job_id = "testjob1id"
    resp = client.get(f"/jobs/{job_id}/ssesrc")
    assert resp.status_code == 500


def test_upload_sselog(test_db: Session, test_storage):
    # Arrange
    job_model = _get_job_model(1, JobType.sse)
    test_db.add(job_model)
    test_db.commit()

    job_id = "testjob1id"
    src_body = "program1"
    encoded = base64.b64encode(src_body.encode())
    form_data = {"file": encoded}

    resp = client.patch(f"/jobs/{job_id}/sselog", files=form_data)

    assert resp.status_code == 200
    adapter = TypeAdapter(UploadSselogResponse)
    sselog_resp = adapter.validate_python(resp.json())
    assert sselog_resp.message == "SSE log uploaded"

    # assert uploaded s3 object
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_file_data = test_storage.get(key=f"{job_id}/{log_name}")
    assert base64.b64decode(log_file_data).decode("utf-8") == src_body


def test_upload_sselog_unknown_jobid(test_db: Session):
    # Arrange
    job_model = _get_job_model(1, JobType.sse)
    test_db.add(job_model)
    test_db.commit()

    src_body = "program1"
    encoded = base64.b64encode(src_body.encode())
    form_data = {"file": encoded}

    resp = client.patch("/jobs/anotherjobid/sselog", files=form_data)

    assert resp.status_code == 404


def test_upload_sselog_invalid_jobtype(test_db: Session):
    # Arrange
    job_model = _get_job_model(1, JobType.sampling)
    test_db.add(job_model)
    test_db.commit()

    job_id = "testjob1id"
    src_body = "program1"
    encoded = base64.b64encode(src_body.encode())
    form_data = {"file": encoded}

    resp = client.patch(f"/jobs/{job_id}/sselog", files=form_data)

    assert resp.status_code == 400


def test_update_job_transpiler_info(test_db: Session):
    job_model = _get_job_model(1, JobType.sampling)
    test_db.add(job_model)
    test_db.commit()
    job_id = job_model.id

    transpilerInfo = {
        "updated_field1": "updated_value1",
        "updated_field2": [42, True, "updated_value2"],
        "updated_field3": {"x": {}, "y": None},
    }
    body = UpdateJobTranspilerInfoRequest(**transpilerInfo)
    resp = client.put(f"/jobs/{job_id}/transpiler_info", content=body.model_dump_json())
    assert resp.status_code == 200

    get_resp = client.get(f"/jobs/{job_id}")
    adapter = TypeAdapter(JobDef)
    aft_job = adapter.validate_python(get_resp.json())
    assert get_resp.status_code == 200
    assert aft_job.transpiler_info == transpilerInfo
