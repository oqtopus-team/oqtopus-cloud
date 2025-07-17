import base64
import io
import json
import os
import zipfile
from datetime import datetime
from typing import List
from urllib.parse import urlparse

import boto3
import pytz
from fastapi.testclient import TestClient
from moto import mock_aws
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.schemas.errors import (
    InternalServerErrorResponse,
)

# from oqtopus_cloud.user.routers.jobs import (
#     get_job,
#     get_job_status,
#     get_jobs,
#     model_to_schema,
# )
from oqtopus_cloud.user.schemas.jobs import (
    JobBase,
    JobInfo,
    JobStatus,
    JobType,
    RegisteredJob,
    RegisterJobResponse,
    SubmitJobRequest,
    SubmitJobType,
    SubmittedJob,
)

from pydantic import ValidationError
from pydantic.type_adapter import TypeAdapter
from sqlalchemy import select

client = TestClient(app)


def _get_registered_model(n: int) -> Job:
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
        "created_at": pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 56)),
    }
    return Job(**model_dict)


def _get_submit_body():
    return {
        "name": "submit-job-test",
        "description": "Submit job test",
        "device_id": "Kawasaki",
        "simulator_info": {"this_is": "simulator info"},
        "transpiler_info": {"this_is": "transpiler info"},
        "mitigation_info": {
            "field1": "value1",
            "field2": {
                "subfield1": "value2",
                "subfield2": ["value3", 42, True],
            },
        },
        "job_type": "sampling",
        "shots": 1024,
    }


def _get_submitted_model(n: int) -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "Kawasaki",
        "job_type": "sampling",
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": "submitted",
        "shots": 1000,
        "submitted_at": pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 56)),
        "created_at": pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 56)),
    }
    return Job(**model_dict)


def _get_succeeded_model(n: int) -> Job:
    job = _get_submitted_model(n)
    job.status = "succeeded"
    job.output_files = json.dumps(["result", "transpile_result"])
    job.message = "job completed successfully"
    job.execution_time = 124.56
    job.ready_at= pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 57))
    job.running_at = pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 34, 58))
    job.ended_at = pytz.utc.localize(datetime(2024, 3, 3 + n, 12, 36, 56))
    return job


def assert_job_info_equals(actual: JobInfo, expect: JobInfo):
    for prop in vars(expect):
        if getattr(expect, prop) is None:
            assert getattr(actual, prop) is None
        else:
            assert urlparse(getattr(actual, prop)).path == getattr(expect, prop)


def assert_jobs_equal(actual: JobBase, expect: JobBase):
    for prop in vars(expect):
        if getattr(expect, prop) is None:
            assert getattr(actual, prop) is None
        else:
            if prop != "job_info":
                assert getattr(actual, prop) == getattr(expect, prop)
            else:
                assert_job_info_equals(getattr(actual, prop), getattr(expect, prop))


@mock_aws
def test_register_job(
    test_db,
):
    """_summary_
    Register new job_id with POST /jobs test
    """
    test_db.flush()

    response = client.post("/jobs")
    adapter = TypeAdapter(RegisterJobResponse)
    actual = adapter.validate_python(response.json())

    new_job_id = actual.job_id

    # basic validation of presign URL data
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    assert urlparse(actual.presigned_url.url).path == f"/{bucket_name}"
    assert actual.presigned_url.fields.key == f"{new_job_id}/input.zip"

    # basic validation of DB record
    job_model = test_db.get(Job, new_job_id)
    assert job_model is not None
    assert job_model.name is ""
    assert job_model.status == "registered"
    assert job_model.job_type == "none"
    assert job_model.shots == 0


@mock_aws
def test_submit_job(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test
    """
    test_db.flush()
    test_db.add(_get_registered_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/input.zip", Body="dummy_job_info")

    response = client.post("/jobs/testjob1id/submit", content=json.dumps(_get_submit_body()))
    assert response.status_code == 200

    actual = test_db.get(Job, "testjob1id")

    assert actual is not None
    assert actual.owner == "admin"

    assert actual.name == "submit-job-test"
    assert actual.description == "Submit job test"
    assert actual.device_id == "Kawasaki"
    assert actual.simulator_info == '{"this_is": "simulator info"}'
    assert actual.transpiler_info == '{"this_is": "transpiler info"}'
    assert actual.mitigation_info == '{"field1": "value1", "field2": {"subfield1": "value2", "subfield2": ["value3", 42, true]}}'
    assert actual.job_type == "sampling"
    assert actual.shots == 1024
    assert actual.execution_time is None
    assert actual.submitted_at is not None
    assert actual.ready_at is None
    assert actual.running_at is None
    assert actual.ended_at is None
    assert actual.created_at == datetime(2024, 3, 4, 12, 34, 56)
    assert actual.updated_at == actual.submitted_at


@mock_aws
def test_submit_job_404(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test, job_id not exist
    """
    response = client.post("/jobs/testjob1id/submit", content=json.dumps(_get_submit_body()))
    assert response.status_code == 404
    assert response.json() == {"message": "job not found with the given id"}


@mock_aws
def test_submit_job_400_invalid_status(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test, job already submitted
    """
    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    response = client.post("/jobs/testjob1id/submit", content=json.dumps(_get_submit_body()))
    assert response.status_code == 400
    assert response.json() == {"message": "testjob1id job is not in valid status for submission (valid status for submission: 'registered')"}


@mock_aws
def test_submit_job_400_invalid_device(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test, invalid device
    """
    test_db.flush()
    test_db.get(Device, "Kawasaki").status = "unavailable"
    test_db.add(_get_registered_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    body = _get_submit_body()
    body["device_id"] = "dummy"
    response = client.post("/jobs/testjob1id/submit", content=json.dumps(body))
    assert response.status_code == 400
    assert response.json() == {"message": "device not found"}

    body = _get_submit_body()
    response = client.post("/jobs/testjob1id/submit", content=json.dumps(body))
    assert response.status_code == 400
    assert response.json() == {"message": "device Kawasaki is not available"}


@mock_aws
def test_submit_job_400_missing_job_info(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test, no S3 job_info file
    """
    test_db.flush()
    test_db.add(_get_registered_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    response = client.post("/jobs/testjob1id/submit", content=json.dumps(_get_submit_body()))
    assert response.status_code == 400
    assert response.json() == {"message": "job information input for testjob1id job not found"}


@mock_aws
def test_submit_job_422_invalid_input(
    test_db,
):
    """_summary_
    Complete job submission with POST /jobs/{job_id}/submit test: try submit values valid only for newly registered jobs
    """
    test_db.flush()
    test_db.add(_get_registered_model(1))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/input.zip", Body="dummy_job_info")

    body = _get_submit_body()
    body["job_type"] = "none"
    response = client.post("/jobs/testjob1id/submit", content=json.dumps(body))
    assert response.status_code == 422

    body = _get_submit_body()
    body["shots"] = 0
    response = client.post("/jobs/testjob1id/submit", content=json.dumps(body))
    assert response.status_code == 422


@mock_aws
def test_get_job_404(
    test_db,
):
    """_summary_

    Args:
            test_db (_type_): _description_
    """
    print(test_db)  # => 1
    response = client.get("/jobs/e8a60c14-8838-46c9-816a-30191d6ab517")
    assert response.status_code == 404
    assert response.json() == {"message": "job not found with the given id"}


@mock_aws
def test_get_jobs_simple(
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.add(_get_succeeded_model(3))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs")
    adapter = TypeAdapter(List[SubmittedJob | RegisteredJob])
    actual = adapter.validate_python(response.json())

    expect = [
        SubmittedJob(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(input=f"/{bucket_name}/testjob1id/input.zip"),
            transpiler_info={"this_is": "transpiler_info"},
            simulator_info={"this_is": "simulator_info"},
            mitigation_info={
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            },
            status=JobStatus.submitted,
            shots=1000,
            execution_time=None,
            submitted_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
        RegisteredJob(
            job_id="testjob2id",
            name="",
            job_type=JobType.none,
            status=JobStatus.registered,
            shots=0,
            created_at=pytz.utc.localize(datetime(2024, 3, 5, 12, 34, 56)),
        ),
        SubmittedJob(
            job_id="testjob3id",
            name="testjob3",
            description="test job 3",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(input=f"/{bucket_name}/testjob3id/input.zip",
                             result=f"/{bucket_name}/testjob3id/result.zip",
                             transpile_result=f"/{bucket_name}/testjob3id/transpile_result.zip",
                             message="job completed successfully"),
            transpiler_info={"this_is": "transpiler_info"},
            simulator_info={"this_is": "simulator_info"},
            mitigation_info={
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            },
            status=JobStatus.succeeded,
            shots=1000,
            execution_time=124.56,
            submitted_at=pytz.utc.localize(datetime(2024, 3, 6, 12, 34, 56)),
            ready_at=pytz.utc.localize(datetime(2024, 3, 6, 12, 34, 57)),
            running_at=pytz.utc.localize(datetime(2024, 3, 6, 12, 34, 58)),
            ended_at=pytz.utc.localize(datetime(2024, 3, 6, 12, 36, 56)),
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_filtering_fields(
    test_db,
):
    """_summary_
    GET job_id, name, device_id, job_type, shots and status by ASC order
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.add(_get_succeeded_model(3))
    test_db.commit()

    response = client.get("/jobs?fields=job_id%2Cname%2Cdevice_id%2Cjob_type%2Cshots%2Cstatus&order=ASC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob1id",
            device_id="Kawasaki",
            name="testjob1",
            job_type=JobType.sampling,
            shots=1000,
            status=JobStatus.submitted,
        ),
        JobBase(
            job_id="testjob2id",
            name="",
            device_id=None,
            job_type=JobType.none,
            shots=0,
            status=JobStatus.registered,
        ),
        JobBase(
            job_id="testjob3id",
            device_id="Kawasaki",
            name="testjob3",
            job_type=JobType.sampling,
            shots=1000,
            status=JobStatus.succeeded,
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_filtering_job_info(
    test_db,
):
    """_summary_
    GET job_info (job_info requires dedicated handling as it is not stored in DB)
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.add(_get_succeeded_model(3))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs?fields=job_info&order=ASC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_info=JobInfo(input=f"/{bucket_name}/testjob1id/input.zip"),
        ),
        JobBase(
            job_info=None,
        ),
        JobBase(job_info=JobInfo(input=f"/{bucket_name}/testjob3id/input.zip",
                                 result=f"/{bucket_name}/testjob3id/result.zip",
                                 transpile_result=f"/{bucket_name}/testjob3id/transpile_result.zip",
                                 message="job completed successfully"),
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_all_fields(test_db):
    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    # This is the request sent from oqtopus-frontend
    response = client.get(
        "jobs?fields=job_id%2Cname%2Cdescription%2Cdevice_id%2Cjob_info%2Ctranspiler_info%2Csimulator_info%2Cmitigation_info%2Cjob_type%2Cshots%2Cstatus&page=1&size=20&order=DESC"
    )
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    assert response.status_code == 200
    assert len(actual) == 2


@mock_aws
def test_get_jobs_invalid_fields(
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    response = client.get("/jobs?fields=XXX%2Cstatus%2CYYY&order=ASC")
    actual = response.json()
    expect = json.loads(
        InternalServerErrorResponse(
            message=f"fields {["XXX", "YYY"]} is invalid"
        ).body.decode()
    )

    assert response.status_code == 500
    assert actual == expect


@mock_aws
def test_get_jobs_filtering_start_time(
    test_db,
):
    """_summary_
    filterling startime, expect only testjob2 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    response = client.get(
        "/jobs?start_time=2024-03-05T07%3A04%3A24%2B09%3A00&order=ASC"
    )
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob2id",
            name="",
            job_type=JobType.none,
            status=JobStatus.registered,
            shots=0,
            created_at=pytz.utc.localize(datetime(2024, 3, 5, 12, 34, 56)),
        ),
    ]

    assert response.status_code == 200
    assert len(actual) == len(expect)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_filtering_end_time(
    test_db,
):
    """_summary_
    filterling end_time, expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs?end_time=2024-03-05T07%3A04%3A24%2B09%3A00&order=ASC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(input=f"/{bucket_name}/testjob1id/input.zip"),
            transpiler_info={"this_is": "transpiler_info"},
            simulator_info={"this_is": "simulator_info"},
            mitigation_info={
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            },
            status=JobStatus.submitted,
            shots=1000,
            execution_time=None,
            submitted_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert len(actual) == len(expect)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_filtering_search_string(
    test_db,
):
    """_summary_
    filterling search string "1", expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(3))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs?q=1&order=ASC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(input=f"/{bucket_name}/testjob1id/input.zip"),
            transpiler_info={"this_is": "transpiler_info"},
            simulator_info={"this_is": "simulator_info"},
            mitigation_info={
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            },
            status=JobStatus.submitted,
            shots=1000,
            execution_time=None,
            submitted_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_desc_order(
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs?order=DESC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob2id",
            name="",
            job_type=JobType.none,
            status=JobStatus.registered,
            shots=0,
            created_at=pytz.utc.localize(datetime(2024, 3, 5, 12, 34, 56)),
        ),
        JobBase(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(input=f"/{bucket_name}/testjob1id/input.zip"),
            transpiler_info={"this_is": "transpiler_info"},
            simulator_info={"this_is": "simulator_info"},
            mitigation_info={
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            },
            status=JobStatus.submitted,
            shots=1000,
            execution_time=None,
            submitted_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert len(actual) == len(expect)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_pagination(
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        if i % 2 == 1:
            test_db.add(_get_submitted_model(i))
        else:
            test_db.add(_get_registered_model(i))
    test_db.commit()

    response = client.get("/jobs?page=1&size=5&fields=job_id")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob1id",
        ),
        JobBase(
            job_id="testjob2id",
        ),
        JobBase(
            job_id="testjob3id",
        ),
        JobBase(
            job_id="testjob4id",
        ),
        JobBase(
            job_id="testjob5id",
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)

    response = client.get("/jobs?page=2&size=5&fields=job_id")
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob6id",
        ),
        JobBase(
            job_id="testjob7id",
        ),
        JobBase(
            job_id="testjob8id",
        ),
        JobBase(
            job_id="testjob9id",
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_get_jobs_all_parameters(
    test_db,
):
    """_summary_
    filtering start_time, end_time, search string, and desc order, expect only testjob3 and testjob2 will be got in this order
    """

    test_db.flush()
    for i in range(1, 20):
        if i % 2 == 1:
            test_db.add(_get_submitted_model(i))
        else:
            test_db.add(_get_registered_model(i))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get(
        "/jobs?fields=job_id%2Cdescription%2Cjob_info&start_time=2024-03-04T16%3A12%3A29%2B09%3A00&end_time=2024-03-14T16%3A12%3A29%2B09%3A00&q=test&page=2&size=3&order=DESC"
    )
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob8id",
            description=None,
            job_info=None,
        ),
        JobBase(
            job_id="testjob7id",
            description="test job 7",
            job_info=JobInfo(input=f"/{bucket_name}/testjob7id/input.zip"),
        ),
        JobBase(
            job_id="testjob6id",
            description=None,
            job_info=None,
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)

    response = client.get(
        "/jobs?fields=job_id%2Cdescription%2Cjob_info&start_time=2024-03-04T16%3A12%3A29%2B09%3A00&end_time=2024-03-14T16%3A12%3A29%2B09%3A00&q=test&page=4&size=3&order=DESC"
    )
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_id="testjob2id",
            description=None,
            job_info=None,
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


@mock_aws
def test_job_sortedness(test_db):
    def is_sorted(xs: list[str]) -> bool:
        return xs == sorted(xs)

    test_db.flush()
    job_ids: list[str] = []
    for n in range(1, 10):
        register_resp = client.post("/jobs")
        job_id = RegisterJobResponse.model_validate(register_resp.json()).job_id
        job_ids.append(job_id)

    assert is_sorted(job_ids)


@mock_aws
def test_get_get(test_db):
    """_summary_
    Test for **the invariance of get and get**:
    retrieving jobs twice should have the same effect on the
    overall state as retrieving them once. In other words,
    the retrieval process must be idempotent.
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.commit()

    sql = select(Job).order_by(Job.created_at)

    resp1 = client.get(f"/jobs/{_get_submitted_model(1).id}")
    assert resp1.status_code == 200
    before_db = test_db.execute(sql).scalars().all()

    resp2 = client.get(f"/jobs/{_get_submitted_model(1).id}")
    assert resp2.status_code == 200
    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft


@mock_aws
def test_register_submit_get(
    test_db,
):
    """_summary_
    Test for **the invariance of register, submit and get**:
    retrieving the job using the ID returned by the register request
    should yield the exact job that was registered and submitted.

    Args:
            test_db (_type_): _description_
    """
    test_db.flush()

    # Registering
    reg_response = client.post("/jobs")
    adapter = TypeAdapter(RegisterJobResponse)
    reg_response_json = adapter.validate_python(reg_response.json())

    job_id = reg_response_json.job_id

    # Get newly registered job
    get_resp = client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 200
    get_resp_json = RegisteredJob.model_validate(get_resp.json())

    assert get_resp_json.name is ""
    assert get_resp_json.status == "registered"
    assert get_resp_json.job_type == "none"
    assert get_resp_json.shots == 0

    # Upload job info
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"{job_id}/input.zip", Body="dummy_job_info")

    # Submitting
    sub_response = client.post(f"/jobs/{job_id}/submit", content=json.dumps(_get_submit_body()))
    assert sub_response.status_code == 200

    # Get submitted job
    get_resp = client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 200
    get_resp_json = SubmittedJob.model_validate(get_resp.json())

    # And these job properties should be same as _get_submit_body().
    assert get_resp_json.name == "submit-job-test"
    assert get_resp_json.description == "Submit job test"
    assert get_resp_json.device_id == "Kawasaki"
    assert get_resp_json.simulator_info == {"this_is": "simulator info"}
    assert get_resp_json.transpiler_info == {"this_is": "transpiler info"}
    assert get_resp_json.mitigation_info == {"field1": "value1", "field2": {"subfield1": "value2", "subfield2": ["value3", 42, True]}}
    assert get_resp_json.job_type == "sampling"
    assert get_resp_json.shots == 1024


@mock_aws
def test_register_submit_cancel_delete(test_db):
    """_summary_
    Test for **the invariance of submit and delete**:
    submitting a job and then sequentially deleting it should result in no remaining effects."

    Args:
            test_db (_type_): _description_
    """
    sql = select(Job).order_by(Job.created_at)
    before_db = test_db.execute(sql).scalars().all()

    # Registering
    reg_response = client.post("/jobs")
    adapter = TypeAdapter(RegisterJobResponse)
    reg_response_json = adapter.validate_python(reg_response.json())

    job_id = reg_response_json.job_id

    # Upload job info
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"{job_id}/input.zip", Body="dummy_job_info")

    # Submitting
    submit_resp = client.post(f"/jobs/{job_id}/submit", content=json.dumps(_get_submit_body()))
    assert submit_resp.status_code == 200

    # Deleting the job of returned job_id (Before deleting, canceling is required)
    cancel_resp = client.post(f"/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200

    # After cancelling, the same cancel request returs 200
    cancel_resp = client.post(f"/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200

    delete_resp = client.delete(f"/jobs/{job_id}")
    assert delete_resp.status_code == 200

    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft


def test_submit_job_shots_boundary(test_db):
    """_summary_
    Test for checking out of range shots
    """

    error_title = ""
    try:
        SubmitJobRequest(
            name="submit-job-test",
            device_id="Kawasaki",
            job_type=SubmitJobType.sampling,
            shots=int(1e7) + 1,
        )
    except ValidationError as e:
        error_title = e.title

    # expcet to raise ValidationError by pydantic
    assert error_title == "SubmitJobRequest"

    error_title = ""
    try:
        SubmitJobRequest(
            name="submit-job-test",
            device_id="Kawasaki",
            job_type=SubmitJobType.sampling,
             shots=int(1e7),
        )
    except ValidationError as e:
        error_title = e.title

    # expcet no ValidationError
    assert error_title == ""


@mock_aws
def test_delete_job(
    test_db,
    test_storage
):
    """_summary_
    Test for delete job and job's resources from storage
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    test_storage.put(key="testjob1id/oqtopus_test_program.py", data=b"program1")
    test_storage.put(key="testjob1id/oqtopus_test_log.log", data=b"log1")
    test_storage.put(key="testjob2id/oqtopus_test_program.py", data=b"program2")
    test_storage.put(key="testjob2id/oqtopus_test_log.log", data=b"log2")

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    job = test_db.get(Job, "testjob1id")
    assert job is None

    object_keys = [key for key in test_storage.prefix(prefix="testjob1id")]
    assert object_keys == []

    # objects = test_storage.prefix(prefix="testjob2id")
    # assert len(objects) == 2
    # assert object in [
    #     "testjob2id/oqtopus_test_program.py",
    #     "testjob2id/oqtopus_test_log.log",
    # ]
    # assert objects["Contents"][1]["Key"] in [
    #     "testjob2id/oqtopus_test_program.py",
    #     "testjob2id/oqtopus_test_log.log",
    # ]


def test_delete_job_no_storage_folder(
    test_db,
    test_storage
):
    """_summary_
    Test for delete job and job's resources from storage
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    job = test_db.get(Job, "testjob1id")
    assert job is None

    object_keys = [key for key in test_storage.prefix(prefix="testjob1id")]
    assert object_keys == []


def test_delete_job_empty_storage_folder(
    test_db,
    test_storage
):
    """_summary_
    Test for delete job and job's resources from storage
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    test_storage.put(key="testjob1id/", data=b"program1")

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    assert not test_storage.does_exist("testjob1id")

    job = test_db.get(Job, "testjob1id")
    assert job is None
