import json
import os
from datetime import datetime
from typing import List
from urllib.parse import urlparse

import boto3
from fastapi.testclient import TestClient
from moto import mock_aws
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.job import (
    Job,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.schemas.jobs import (
    JobDef,
    JobInfoUploadPresignedURL,
    JobStatus,
    JobType,
    UpdateJobTranspilerInfoRequest,
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


def _get_registered_job_model(n: int) -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": "",
        "device_id": "null",
        "job_type": "none",
        "transpiler_info": "null",
        "simulator_info": "null",
        "mitigation_info": "null",
        "status": "registered",
        "shots": 0,
        "created_at": datetime(2024, 3, 3 + n, 12, 34, 56),
    }
    return Job(**model_dict)


def _get_job_model(
    n: int, jt: JobType = JobType.sampling, status: JobStatus = JobStatus.ready
) -> Job:
    mode_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "SC",
        "job_type": jt.value,
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
    return Job(**mode_dict)


@mock_aws
def test_get_jobs(test_db: Session):
    test_db.flush()
    test_db.add(_get_registered_job_model(0))
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    # check response
    response = client.get("/jobs?device_id=SC")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert len(actual) == 2

    assert actual[0].job_id == "testjob1id"
    assert urlparse(actual[0].input).path == f"/{bucket_name}/testjob1id/input.zip"
    assert actual[0].status == JobStatus.ready

    assert actual[1].job_id == "testjob2id"
    assert urlparse(actual[1].input).path == f"/{bucket_name}/testjob2id/input.zip"
    assert actual[1].status == JobStatus.ready

    # check status update in db
    assert test_db.get(Job, "testjob1id").status == "ready"
    assert test_db.get(Job, "testjob2id").status == "ready"


@mock_aws
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


@mock_aws
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


@mock_aws
def test_get_jobs_with_timestamp(test_db: Session):
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get(
        "/jobs?device_id=SC&timestamp=2024-03-11T07%3A04%3A24%2B09%3A00"
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


@mock_aws
def test_get_jobs_with_max_results(test_db: Session):
    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_job_model(i))
    test_db.add(_get_device_model())
    test_db.commit()

    response = client.get("/jobs?device_id=SC&max_results=3")
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


@mock_aws
def test_get_job(test_db: Session):
    test_db.flush()
    test_db.add(_get_registered_job_model(0))
    test_db.add(_get_job_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs/testjob1id")
    adapter = TypeAdapter(JobDef)
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert actual.job_id == "testjob1id"
    assert urlparse(actual.input).path == f"/{bucket_name}/testjob1id/input.zip"

    assert actual.status == JobStatus.ready
    assert test_db.get(Job, "testjob1id").status == "ready"


@mock_aws
def test_job_upload(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1))
    test_db.add(_get_job_model(2, jt=JobType.multi_manual))
    test_db.add(_get_job_model(3, jt=JobType.sse))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,result")
    adapter = TypeAdapter(list[JobInfoUploadPresignedURL])
    actual = adapter.validate_python(response.json())

    assert len(actual) == 2
    assert urlparse(actual[0].url).path == urlparse(actual[1].url).path == f"/{bucket_name}"
    assert actual[0].fields is not None
    assert actual[0].fields.key == f"testjob1id/transpile_result.zip"
    assert actual[1].fields is not None
    assert actual[1].fields.key == f"testjob1id/result.zip"

    response = client.get("/jobs/testjob2id/upload?items=combined_program,transpile_result,result")
    actual = adapter.validate_python(response.json())

    assert len(actual) == 3
    assert urlparse(actual[0].url).path == urlparse(actual[1].url).path == urlparse(actual[2].url).path == f"/{bucket_name}"
    assert actual[0].fields is not None
    assert actual[0].fields.key == f"testjob2id/combined_program.zip"
    assert actual[1].fields is not None
    assert actual[1].fields.key == f"testjob2id/transpile_result.zip"
    assert actual[2].fields is not None
    assert actual[2].fields.key == f"testjob2id/result.zip"

    response = client.get("/jobs/testjob3id/upload?items=transpile_result,result,sse_log")
    actual = adapter.validate_python(response.json())

    assert len(actual) == 3
    assert urlparse(actual[0].url).path == urlparse(actual[1].url).path == urlparse(actual[2].url).path == f"/{bucket_name}"
    assert actual[0].fields is not None
    assert actual[0].fields.key == f"testjob3id/transpile_result.zip"
    assert actual[1].fields is not None
    assert actual[1].fields.key == f"testjob3id/result.zip"
    assert actual[2].fields is not None
    assert actual[2].fields.key == f"testjob3id/sse_log.zip"


@mock_aws
def test_job_upload_404(test_db: Session):
    test_db.flush()

    response = client.get("/jobs/testjob1id/upload?items=transpile_result,result")
    assert response.status_code == 404
    assert response.json()["message"] == "Job not found"


@mock_aws
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


@mock_aws
def test_update_job_status(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.ready))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
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

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key="testjob1id/result.zip", Body="dummy_content")
    s3client.put_object(Bucket=bucket_name, Key="testjob1id/transpile_result.zip", Body="dummy_content")

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


@mock_aws
def test_update_job_invalid_status_transitions(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.submitted))
    test_db.add(_get_job_model(2, status=JobStatus.ready))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
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

    model = test_db.get(Job, "testjob2id")
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


@mock_aws
def test_update_job_status_invalid_output_files_1(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
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


@mock_aws
def test_update_job_status_invalid_output_files_2(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
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


@mock_aws
def test_update_job_status_missing_output_file(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
    assert model is not None

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

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


@mock_aws
def test_update_job_status_invalid_execution_time(test_db: Session):
    test_db.flush()
    test_db.add(_get_job_model(1, status=JobStatus.running))
    test_db.commit()

    model = test_db.get(Job, "testjob1id")
    assert model is not None

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key="testjob1id/result.zip", Body="dummy_content")
    s3client.put_object(Bucket=bucket_name, Key="testjob1id/transpile_result.zip", Body="dummy_content")

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


@mock_aws
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
