import json
import os
from datetime import datetime
from typing import List
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.job import (
    Job as JobModel,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
)
from oqtopus_cloud.provider.schemas.jobs import (
    Job,
    JobDef,
    JobInfoUploadPresignedURL,
    JobStatus,
    JobType,
    UpdateJobTranspilerInfoRequest,
)
from pydantic.type_adapter import TypeAdapter
from sqlalchemy.orm.session import Session
from zoneinfo import ZoneInfo

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
        "id": "SC",
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


def _get_registered_job_model(n: int) -> JobModel:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": "",
        "device_id": "null",
        "job_type": "none",
        "job_info": "",
        "transpiler_info": "null",
        "simulator_info": "null",
        "mitigation_info": "null",
        "status": "registered",
        "shots": 0,
        "created_at": datetime(2024, 3, 3 + n, 12, 34, 56),
    }
    return JobModel(**model_dict)


def _get_job_model(
    n: int, jt: JobType = JobType.sampling, status: JobStatus = JobStatus.ready
) -> JobModel:
    mode_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "SC",
        "job_type": jt.value,
        "job_info": "",
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": status.value,
        "shots": 1000,
        "submitted_at": datetime(2024, 3, 4 + n, 12, 34, 56),
        "created_at": datetime(2024, 3, 4 + n, 12, 34, 56),
    }

    return JobModel(**mode_dict)


def test_get_jobs(test_db: Session):
    test_db.flush()
    test_db.add(_get_registered_job_model(0))
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2))
    test_db.commit()

    storage_base = os.environ["STORAGE_LOCAL_BASE_PATH"]

    # check response
    response = client.get("/jobs?device_id=SC")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert len(actual) == 2

    assert actual[0].job_id == "testjob1id"
    assert urlparse(actual[0].input).path == f"{storage_base}/testjob1id/input.zip"
    assert actual[0].status == JobStatus.ready

    assert actual[1].job_id == "testjob2id"
    assert urlparse(actual[1].input).path == f"{storage_base}/testjob2id/input.zip"
    assert actual[1].status == JobStatus.ready

    # check status update in db
    assert test_db.get(JobModel, "testjob1id").status == "ready"
    assert test_db.get(JobModel, "testjob2id").status == "ready"


def test_get_jobs_ignore_illegal_job(
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2))
    # job3 has unexpected job_type
    job_3 = _get_job_model(3)
    job_3.job_type = "none"
    test_db.add(job_3)
    test_db.commit()

    response = client.get("/jobs?device_id=SC")
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

    storage_base = os.environ["STORAGE_LOCAL_BASE_PATH"]

    response = client.get(
        "/jobs?device_id=SC&fields=input"
    )
    adapter = TypeAdapter(List[Job])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200

    assert len(actual) == 2
    assert actual[0].job_id == "testjob1id"
    assert actual[0].name == "testjob1"
    assert actual[0].job_type == JobType.sampling
    assert actual[0].status == JobStatus.ready
    assert urlparse(actual[0].input).path == f"{storage_base}/testjob1id/input.zip"
    assert actual[0].transpiler_info == {"this_is": "transpiler_info"}

    assert actual[1].job_id == "testjob2id"
    assert actual[1].name == "testjob2"
    assert actual[1].job_type == JobType.sampling
    assert actual[1].status == JobStatus.ready
    assert urlparse(actual[1].input).path == f"{storage_base}/testjob2id/input.zip"
    assert actual[1].transpiler_info == {"this_is": "transpiler_info"}


def test_get_jobs_all_fields(test_db):
    test_db.flush()
    test_db.add(_get_job_model(1, JobType.sampling))
    test_db.add(_get_job_model(2, JobType.sampling))
    test_db.commit()

    # This is the request sent from oqtopus-frontend
    response = client.get(
        "jobs?device_id=SC&fields=job_id,name,description,device_id,input,transpiler_info,simulator_info,mitigation_info,job_type,shots,status"
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


def test_get_jobs_with_status(test_db: Session):
    test_db.flush()
    for i in range(1, 4):
        test_db.add(_get_job_model(i, status=JobStatus.running))
    test_db.add(_get_job_model(4, status=JobStatus.ready))
    test_db.add(_get_job_model(5, status=JobStatus.submitted))
    test_db.add(_get_registered_job_model(6))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC&status=running")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    expect = [
        "testjob1id",
        "testjob2id",
        "testjob3id",
    ]

    assert response.status_code == 200
    assert len(actual) == 3
    for act, exp_job_id in zip(actual, expect):
        assert act.job_id == exp_job_id


def test_get_jobs_with_timestamp(test_db: Session):
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get(
        "/jobs?device_id=SC&timestamp=2024-03-11T07%3A04%3A24Z"
    )
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    expect = [
        "testjob7id",
        "testjob8id",
        "testjob9id",
    ]

    assert response.status_code == 200
    assert len(actual) == 3
    for act, exp_job_id in zip(actual, expect):
        assert act.job_id == exp_job_id



def test_get_jobs_limit(test_db: Session):
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC&limit=3")
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
    test_db.flush()
    test_db.add(_get_registered_job_model(0))
    test_db.add(_get_job_model(1))
    test_db.commit()

    storage_base = os.environ["STORAGE_LOCAL_BASE_PATH"]

    response = client.get("/jobs/testjob1id")
    adapter = TypeAdapter(JobDef)
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert actual.job_id == "testjob1id"
    assert urlparse(actual.input).path == f"{storage_base}/testjob1id/input.zip"

    assert actual.status == JobStatus.ready
    assert test_db.get(JobModel, "testjob1id").status == "ready"


def test_job_upload(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2, jt=JobType.multi_manual))
    test_db.add(_get_job_model(3, jt=JobType.sse))
    test_db.commit()

    storage_base = os.environ["STORAGE_LOCAL_BASE_PATH"]

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,result")
    adapter = TypeAdapter(list[JobInfoUploadPresignedURL])
    actual = adapter.validate_python(response.json())

    assert len(actual) == 2
    assert urlparse(actual[0].url).path == f"{storage_base}/testjob1id/transpile_result.zip"
    assert urlparse(actual[1].url).path == f"{storage_base}/testjob1id/result.zip"

    response = client.get("/jobs/testjob2id/upload?items=combined_program,transpile_result,result")
    actual = adapter.validate_python(response.json())

    assert len(actual) == 3
    assert urlparse(actual[0].url).path == f"{storage_base}/testjob2id/combined_program.zip"
    assert urlparse(actual[1].url).path == f"{storage_base}/testjob2id/transpile_result.zip"
    assert urlparse(actual[2].url).path == f"{storage_base}/testjob2id/result.zip"

    response = client.get("/jobs/testjob3id/upload?items=transpile_result,result,sse_log")
    actual = adapter.validate_python(response.json())

    assert len(actual) == 3
    assert urlparse(actual[0].url).path == f"{storage_base}/testjob3id/transpile_result.zip"
    assert urlparse(actual[1].url).path == f"{storage_base}/testjob3id/result.zip"
    assert urlparse(actual[2].url).path == f"{storage_base}/testjob3id/sse_log.zip"


def test_job_upload_404(test_db: Session):
    test_db.flush()

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,result")
    assert response.status_code == 404
    assert response.json()["message"] == "Job not found"


def test_job_upload_400(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1))
    test_db.commit()

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,xxx,result")
    assert response.status_code == 400
    assert response.json()["message"] == "Unsupported item(s) for upload: ['xxx']"

    response = client.get("/jobs/testjob1id/upload?items=combined_program,transpile_result,result")
    assert response.status_code == 400
    assert response.json()["message"] == "Unsupported item: combined_program for job type: sampling"

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,result,sse_log")
    assert response.status_code == 400
    assert response.json()["message"] == "Unsupported item: sse_log for job type: sampling"


def test_update_job_status(
    test_db,
    test_storage,
):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.ready))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    body = {
        "status": "running"
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 200
    assert model.status == JobStatus.running
    assert model.running_at is not None
    running_at = model.running_at
    assert model.ended_at is None

    test_storage.put(key="testjob1id/result.zip", data=b"dummy_content")
    test_storage.put(key="testjob1id/transpile_result.zip", data=b"dummy_content")

    body = {
        "status": "succeeded",
        "output_files": ["testjob1id/result.zip", "testjob1id/transpile_result.zip"],
        "message": "job succeeded",
        "execution_time": 15.8
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 200
    assert model.status == JobStatus.succeeded
    assert model.output_files == json.dumps(["result", "transpile_result"])
    assert model.message == "job succeeded"
    assert model.execution_time == 15.8
    assert model.running_at == running_at
    assert model.ended_at is not None


def test_update_job_invalid_status_transitions(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.submitted))
    test_db.add(_get_job_model(2, status=JobStatus.ready))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    body = {
        "status": "running"
    }
    resp = client.patch(
        f"/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 409
    assert resp.json()["message"] == "The specified job is not a status that allows transition to the status: Status.running"
    assert model.status == JobStatus.submitted

    model = test_db.get(JobModel, "testjob2id")
    assert model is not None

    body = {
        "status": "succeeded"
    }
    resp = client.patch(
        f"/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 409
    assert resp.json()["message"] == "The specified job is not a status that allows transition to the status: Status.succeeded"
    assert model.status == JobStatus.ready
    assert model.output_files is None
    assert model.message is None
    assert model.execution_time is None


def test_update_job_status_invalid_output_files_1(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    body = {
        "status": "succeeded",
        "output_files": ["testjob2id/result.zip", "testjob1id/transpile_result.zip"],
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 409
    assert resp.json()["message"] == "Invalid output file key: testjob2id/result.zip for job_id: testjob1id"
    assert model.status == JobStatus.running
    assert model.output_files is None
    assert model.message is None
    assert model.execution_time is None


def test_update_job_status_invalid_output_files_2(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    body = {
        "status": "succeeded",
        "output_files": ["testjob1id/resultxxx.zip", "testjob1id/transpile_result.zip"],
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 400
    assert resp.json()["message"] == "Invalid output file key: testjob1id/resultxxx.zip"
    assert model.status == JobStatus.running
    assert model.output_files is None
    assert model.message is None
    assert model.execution_time is None


def test_update_job_status_missing_output_file(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    body = {
        "status": "succeeded",
        "output_files": ["testjob1id/result.zip", "testjob1id/transpile_result.zip"],
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 400
    assert resp.json()["message"] == "testjob1id/result.zip not found"
    assert model.status == JobStatus.running
    assert model.output_files is None
    assert model.message is None
    assert model.execution_time is None


def test_update_job_status_invalid_execution_time(
    test_db,
    test_storage,
):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(JobModel, "testjob1id")
    assert model is not None

    test_storage.put(key="testjob1id/result.zip", data=b"dummy_content")
    test_storage.put(key="testjob1id/transpile_result.zip", data=b"dummy_content")

    body = {
        "status": "succeeded",
        "output_files": ["testjob1id/result.zip", "testjob1id/transpile_result.zip"],
        "execution_time": -15.8
    }
    resp = client.patch(
        "/jobs/testjob1id/status",
        content=json.dumps(body),
    )
    assert resp.status_code == 400
    assert model.status == JobStatus.running
    assert model.output_files is None
    assert model.message is None
    assert model.execution_time is None


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
