import base64
import io
import json
import os
import zipfile
from datetime import datetime
from typing import List

import boto3
import pytz
from fastapi.testclient import TestClient
from moto import mock_aws
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
    JobStatus,
    JobType,
    RegisteredJob,
    RegisterJobResponse,
    SubmittedJob,
    SubmitJobRequest,
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


def assert_jobs_equal(actual: SubmittedJob, expect: SubmittedJob):
    for prop in vars(expect):
        if getattr(expect, prop) is None:
            assert getattr(actual, prop) is None
        else:
            if prop != "job_info":
                assert getattr(actual, prop) == getattr(expect, prop)
            else:
                assert getattr(actual, prop).startswith(getattr(expect, prop))


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
    region = boto3.client('s3').meta.region_name
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    assert actual.presigned_url.url == f"https://s3.{region}.amazonaws.com/{bucket_name}"
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
    Complete job submission with PATCH /jobs/{job_id} test
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

    response = client.patch("/jobs/testjob1id", content=json.dumps(_get_submit_body()))
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

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/input.zip")


def test_submit_job_404(
    test_db,
):
    """_summary_
    Complete job submission with PATCH /jobs/{job_id} test, job_id not exist
    """
    response = client.patch("/jobs/e8a60c14-8838-46c9-816a-30191d6ab517", content=json.dumps(_get_submit_body()))
    assert response.status_code == 404
    assert response.json() == {"message": "job not found with the given id"}


@mock_aws
def test_submit_job_400_invalid_status(
    test_db,
):
    """_summary_
    Complete job submission with PATCH /jobs/{job_id} test, job already submitted
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

    response = client.patch("/jobs/testjob1id", content=json.dumps(_get_submit_body()))
    assert response.status_code == 400
    assert response.json() == {"message": "testjob1id job is not in valid status for submission (valid status for submission: 'registered')"}


@mock_aws
def test_submit_job_400_missing_job_info(
    test_db,
):
    """_summary_
    Complete job submission with PATCH /jobs/{job_id} test, no S3 job_info file
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

    response = client.patch("/jobs/testjob1id", content=json.dumps(_get_submit_body()))
    assert response.status_code == 400
    assert response.json() == {"message": "job information for testjob1id job not found"}


@mock_aws
def test_submit_job_422_invalid_input(
    test_db,
):
    """_summary_
    Complete job submission with PATCH /jobs/{job_id} test: try submit values valid only for newly registered jobs
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
    response = client.patch("/jobs/testjob1id", content=json.dumps(body))
    assert response.status_code == 422

    body = _get_submit_body()
    body["shots"] = 0
    response = client.patch("/jobs/testjob1id", content=json.dumps(body))
    assert response.status_code == 422


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


def test_get_jobs_simple(
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()

    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
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
            job_info=f"https://s3.ap-northeast-1.amazonaws.com/{bucket_name}/testjob1id/input.zip",
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
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


def test_get_jobs_filtering_fields(
    test_db,
):
    """_summary_
    GET job_id, name, device_id, job_type, shots and status by ASC order
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
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
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


def test_get_jobs_filtering_job_info(
    test_db,
):
    """_summary_
    GET job_info (job_info requires dedicated handling as it is not stored in DB)
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_registered_model(2))
    test_db.commit()

    bucket_name = os.environ["OQTOPUS_BUCKET"]

    response = client.get("/jobs?fields=job_info&order=ASC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())

    expect = [
        JobBase(
            job_info=f"https://s3.ap-northeast-1.amazonaws.com/{bucket_name}/testjob1id/input.zip"
        ),
        JobBase(
            job_info=None,
        ),
    ]

    assert response.status_code == 200
    assert len(expect) == len(actual)
    for (act, exp) in zip(actual, expect):
        assert_jobs_equal(act, exp)


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


def test_get_jobs_filtering_start_time(
    test_db,
):
    """_summary_
    filterling startime, expect only testjob2 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_submitted_model(2))
    test_db.commit()

    response = client.get(
        "/jobs?start_time=2024-03-05T07%3A04%3A24%2B09%3A00&order=ASC"
    )
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob2id",
            name="testjob2",
            description="test job 2",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(program=["code"]),
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
            submitted_at=pytz.utc.localize(datetime(2024, 3, 5, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_filtering_end_time(
    test_db,
):
    """_summary_
    filterling end_time, expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_submitted_model(2))
    test_db.commit()

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
            job_info=JobInfo(program=["code"]),
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
    assert actual == expect


def test_get_jobs_filtering_search_string(
    test_db,
):
    """_summary_
    filterling search string "1", expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_submitted_model(2))
    test_db.commit()

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
            job_info=JobInfo(program=["code"]),
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
    assert actual == expect


def test_get_jobs_desc_order(
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.add(_get_submitted_model(2))
    test_db.commit()

    response = client.get("/jobs?order=DESC")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob2id",
            name="testjob2",
            description="test job 2",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(program=["code"]),
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
            submitted_at=pytz.utc.localize(datetime(2024, 3, 5, 12, 34, 56)),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
        JobBase(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(program=["code"]),
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
    assert actual == expect


def test_get_jobs_pagination(
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_submitted_model(i))
    test_db.commit()

    response = client.get("/jobs?page=3&size=3&fields=job_id")
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
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
    assert actual == expect


def test_get_jobs_all_parameters(
    test_db,
):
    """_summary_
    filtering start_time, end_time, search string, and desc order, expect only testjob3 and testjob2 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_submitted_model(i))
    test_db.commit()

    response = client.get(
        "/jobs?fields=job_id%2Cdescription%2Cjob_info&start_time=2024-03-04T16%3A12%3A29%2B09%3A00&end_time=2024-03-08T16%3A12%3A29%2B09%3A00&q=test&order=DESC&page=2&size=2"
    )
    adapter = TypeAdapter(List[JobBase])
    actual = adapter.validate_python(response.json())
    expect = [
        JobBase(
            job_id="testjob3id",
            description="test job 3",
            job_info=JobInfo(program=["code"]),
        ),
        JobBase(
            job_id="testjob2id",
            description="test job 2",
            job_info=JobInfo(program=["code"]),
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_job_sortedness(test_db):
    def mk_job(n: int) -> SubmitJobRequest:
        return SubmitJobRequest(
            name=f"test-job-{n}",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=SubmitJobInfo(program=["code"]),
            simulator_info={"this_is": "simulator info"},
            transpiler_info={"this_is": "transpiler info"},
            mitigation_info={"this_is": "mitigation info"},
            shots=1000,
        )

    def is_sorted(xs: list[str]) -> bool:
        return xs == sorted(xs)

    test_db.flush()
    job_ids: list[str] = []
    for n in range(1, 10):
        submit_resp = client.post("/jobs", content=mk_job(n).model_dump_json())
        print(f"submit_resp={submit_resp.json()}")
        job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
        job_ids.append(job_id)

    assert is_sorted(job_ids)


def test_get_jobs_handler(
    test_db,
):
    """_summary_

    Args:
            test_db (_type_): _description_
    """

    test_db.flush()
    test_db.add(_get_submitted_model(1))
    test_db.commit()

    response = client.get("/jobs")
    assert response.status_code == 200

    adapter = TypeAdapter(List[SubmittedJob])
    jobs = adapter.validate_python(response.json())

    expected = SubmittedJob(
        job_id="testjob1id",
        name="testjob1",
        description="test job 1",
        device_id="Kawasaki",
        job_type=JobType.sampling,
        job_info=JobInfo(program=["code"]),
        transpiler_info={"this_is": "transpiler_info"},
        simulator_info={"this_is": "simulator_info"},
        mitigation_info={"field1": "value1", "field2": "value2", "field3": "value3"},
        status=JobStatus.submitted,
        shots=1000,
        execution_time=None,
        submitted_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
        ready_at=None,
        running_at=None,
        ended_at=None,
    )
    assert jobs[0] == expected


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


def test_submit_get(
    test_db,
):
    """_summary_
    Test for **the invariance of submit and get**:
    retrieving the job using the ID returned by the submit request
    should yield the exact job that was submitted.

    Args:
            test_db (_type_): _description_
    """
    test_db.flush()
    test_db.commit()

    body = SubmitJobRequest(
        name="submit-job-test",
        description="Submit job test",
        device_id="Kawasaki",
        job_type=JobType.sampling,
        job_info=SubmitJobInfo(program=["codecodecode"]),
        mitigation_info={
            "field1": "value1",
            "field2": {
                "subfield1": "value2",
                "subfield2": ["value3", 42, True],
            },
        },
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        shots=1024,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = SubmittedJob.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None


def test_submit_cancel_delete(test_db):
    """_summary_
    Test for **the invariance of submit and delete**:
    submitting a job and then sequentially deleting it should result in no remaining effects."

    Args:
            test_db (_type_): _description_
    """
    sql = select(Job).order_by(Job.created_at)
    before_db = test_db.execute(sql).scalars().all()

    body = SubmitJobRequest(
        name="submit-job-test",
        description="Submit job test",
        device_id="Kawasaki",
        job_type=JobType.sampling,
        job_info=SubmitJobInfo(program=["codecodecode"]),
        mitigation_info={
            "field1": "value1",
            "field2": {
                "subfield1": "value2",
                "subfield2": ["value3", 42, True],
            },
        },
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        shots=1024,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id

    # Deleting the job of reteurned job_id (Before deleting, canceling is required)
    cancel_resp = client.post(f"/jobs/{resp_job_id}/cancel")
    assert cancel_resp.status_code == 200

    # After cancelling, the same cancel request returs 200
    cancel_resp = client.post(f"/jobs/{resp_job_id}/cancel")
    assert cancel_resp.status_code == 200

    delete_resp = client.delete(f"/jobs/{resp_job_id}")
    assert delete_resp.status_code == 200

    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft


def test_submit_job_compat_error(test_db):
    """_summary_
    Test for **the invariance of submit and delete**:
    submitting a job and then sequentially deleting it should result in no remaining effects."

    Args:
            test_db (_type_): _description_
    """

    body = SubmitJobRequest(
        name="submit-job-test",
        description="Submit job test",
        device_id="Kawasaki",
        job_type=JobType.estimation,
        job_info=SubmitJobInfo(program=["codecodecode"]),
        mitigation_info={
            "field1": "value1",
            "field2": {
                "subfield1": "value2",
                "subfield2": ["value3", 42, True],
            },
        },
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        shots=1024,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 400


def test_submit_job_shots_boundary(test_db):
    """_summary_
    Test for checking out of range shots
    """

    try:
        SubmitJobRequest(
            name="submit-job-test",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=SubmitJobInfo(program=["codecodecode"]),
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
            job_type=JobType.sampling,
            job_info=SubmitJobInfo(program=["codecodecode"]),
            shots=int(1e7),
        )
    except ValidationError as e:
        error_title = e.title

    # expcet no ValidationError
    assert error_title == ""


@mock_aws
def test_get_sselog(
    test_db,
):
    """_summary_
    Test for get sselog
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = "log1"
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}", Body=log_body)

    # expected zip file with base64 encode
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w", compression=zipfile.ZIP_DEFLATED) as zip_data:
        zip_data.writestr(log_name, log_body)
    zip_stream.seek(0)
    zip_bin = zip_stream.read()
    zip_base64 = base64.b64encode(zip_bin).decode("utf-8")

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    actual = adapter.validate_python(response.json())

    expect = {"file": zip_base64, "file_name": "oqtopus_test_sse_log_testjob1id.zip"}

    assert response.status_code == 200
    assert actual == expect

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}")


@mock_aws
def test_get_sselog_invalid_owner(
    test_db,
):
    """_summary_
    Test for get sselog when the job owner is invalid
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    job_model.owner = "user1"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = "log1"
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}", Body=log_body)

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 404

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}")


@mock_aws
def test_get_sselog_unknown_jobid(
    test_db,
):
    """_summary_
    Test for get sselog when the job_id is invalid
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    job_model.id = "anotherjobid"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = "log1"
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}", Body=log_body)

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 404

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}")


@mock_aws
def test_get_sselog_invalid_jobtype(
    test_db,
):
    """_summary_
    Test for get sselog when the job_type is not sse
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sampling"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = "log1"
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}", Body=log_body)

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 400

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}")


@mock_aws
def test_get_sselog_running_job(
    test_db,
):
    """_summary_
    Test for get sselog when the job status is neighter succeeded nor failed
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "running"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = "log1"
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}", Body=log_body)

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 400

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key=f"testjob1id/{log_name}")


@mock_aws
def test_get_sselog_no_log(
    test_db,
):
    """_summary_
    Test for get sselog when the job failed and there is no log file in S3
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "failed"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    response = client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 404


@mock_aws
def test_put_user_program_to_s3(
    test_db,
):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    program = base64.b64encode(b"program1").decode("utf-8")

    body = SubmitJobRequest(
        name="submit-sse-job-test",
        description="Submit sse job test",
        device_id="Kawasaki",
        job_type=JobType.sse,
        job_info=SubmitJobInfo(program=[program]),
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        mitigation_info={"this_is": "mitigation info"},
        shots=1,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = SubmittedJob.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None

    s3object = s3client.get_object(
        Bucket=bucket_name, Key=f"{resp_job_id}/oqtopus_test_program.py"
    )
    assert s3object["Body"].read().decode() == "program1"

    # clean up
    s3client.delete_object(
        Bucket=bucket_name, Key=f"{resp_job_id}/oqtopus_test_program.py"
    )


@mock_aws
def test_put_user_program_to_s3_invalid_program(
    test_db,
):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    program = "invalid_program"  # not base64 encoded

    body = SubmitJobRequest(
        name="submit-sse-job-test",
        description="Submit sse job test",
        device_id="Kawasaki",
        job_type=JobType.sse,
        job_info=SubmitJobInfo(program=[program]),
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        mitigation_info={"this_is": "mitigation info"},
        shots=1,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 500


@mock_aws
def test_put_user_program_to_s3_no_program(
    test_db,
):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    body = SubmitJobRequest(
        name="submit-sse-job-test",
        description="Submit sse job test",
        device_id="Kawasaki",
        job_type=JobType.sse,
        job_info=SubmitJobInfo(program=[]),
        simulator_info={"this_is": "simulator info"},
        transpiler_info={"this_is": "transpiler info"},
        mitigation_info={"this_is": "mitigation info"},
        shots=1,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 500


@mock_aws
def test_delete_s3_folder(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/oqtopus_test_program.py", Body="program1")
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/oqtopus_test_log.log", Body="log1")
    s3client.put_object(Bucket=bucket_name, Key=f"testjob2id/oqtopus_test_program.py", Body="program2")
    s3client.put_object(Bucket=bucket_name, Key=f"testjob2id/oqtopus_test_log.log", Body="log2")

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    objects = s3client.list_objects_v2(Bucket=bucket_name, Prefix="testjob1id")
    assert "Contents" not in objects
    objects = s3client.list_objects_v2(Bucket=bucket_name, Prefix="testjob2id")
    assert "Contents" in objects
    assert len(objects["Contents"]) == 2
    assert objects["Contents"][0]["Key"] in ["testjob2id/oqtopus_test_program.py", "testjob2id/oqtopus_test_log.log"]
    assert objects["Contents"][1]["Key"] in ["testjob2id/oqtopus_test_program.py", "testjob2id/oqtopus_test_log.log"]
    job = test_db.get(Job, "testjob1id")
    assert job is None

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key="testjob2id/oqtopus_test_program.py")
    s3client.delete_object(Bucket=bucket_name, Key="testjob2id/oqtopus_test_log.log")
    s3client.delete_object(Bucket=bucket_name, Key="testjob2id/")
    s3client.delete_bucket(Bucket=bucket_name)


@mock_aws
def test_delete_s3_folder_no_folder(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    objects = s3client.list_objects_v2(Bucket=bucket_name, Prefix="testjob1id")
    assert "Contents" not in objects
    job = test_db.get(Job, "testjob1id")
    assert job is None

    # clean up
    s3client.delete_bucket(Bucket=bucket_name)


@mock_aws
def test_delete_s3_folder_no_file(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/", Body="program1")

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    objects = s3client.list_objects_v2(Bucket=bucket_name, Prefix="testjob1id")
    assert "Contents" not in objects
    job = test_db.get(Job, "testjob1id")
    assert job is None

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key="testjob1id/")
    s3client.delete_bucket(Bucket=bucket_name)


@mock_aws
def test_delete_s3_folder_folder_only(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    bucket_name = os.environ["SSE_BUCKET"]
    s3client = boto3.client("s3")
    s3client.create_bucket(
        Bucket=bucket_name,
        CreateBucketConfiguration={"LocationConstraint": "ap-northeast-1"},
    )
    s3client.put_object(Bucket=bucket_name, Key=f"testjob1id/", Body="program1")

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    objects = s3client.list_objects_v2(Bucket=bucket_name, Prefix="testjob1id")
    assert "Contents" not in objects
    job = test_db.get(Job, "testjob1id")
    assert job is None

    # clean up
    s3client.delete_object(Bucket=bucket_name, Key="testjob1id/")
    s3client.delete_bucket(Bucket=bucket_name)


@mock_aws
def test_delete_s3_not_sse_job(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sampling"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    job = test_db.get(Job, "testjob1id")
    assert job is None


@mock_aws
def test_delete_s3_folder_exception(
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_submitted_model(1)
    job_model.job_type = "sse"
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    # do not create bucket to raise exception

    # Request
    delete_resp = client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 500

    job = test_db.get(Job, "testjob1id")
    assert job is None
