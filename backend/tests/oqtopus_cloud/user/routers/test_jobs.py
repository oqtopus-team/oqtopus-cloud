import base64
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import List

from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
)
from oqtopus_cloud.user.schemas.jobs import (
    GetJobsResponse,
    JobDef,
    JobInfo,
    JobStatus,
    JobType,
    SubmitJobInfo,
    SubmitJobRequest,
    SubmitJobResponse,
)
from pydantic import ValidationError
from pydantic.type_adapter import TypeAdapter
from sqlalchemy import select


def _get_model(n: int, should_change_owner_num: bool = False) -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": f"email_{n}" if should_change_owner_num else "email_1",
        "name": f"testjob{n}",
        "description": f"test job {n}",
        "device_id": "Kawasaki",
        "job_type": "sampling",
        "job_info": json.dumps({"program": ["code"]}),
        "transpiler_info": json.dumps({"this_is": "transpiler_info"}),
        "simulator_info": json.dumps({"this_is": "simulator_info"}),
        "mitigation_info": json.dumps(
            {"field1": "value1", "field2": "value2", "field3": "value3"}
        ),
        "status": "submitted",
        "shots": 1000,
        "submitted_at": datetime(2024, 3, 3 + n, 12, 34, 56, tzinfo=timezone.utc),
        "created_at": datetime(2024, 3, 3 + n, 12, 34, 56, tzinfo=timezone.utc),
    }
    return Job(**model_dict)


def _get_user_model(n: int, available_devices="*") -> User:
    if available_devices != "*":
        available_devices = json.dumps(available_devices)

    model_dict = {
        "id": f"email_{n}",
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "display_name": f"test_user_{n}",
        "userstatus": UserStatus.approved,
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": available_devices,
        "api_token_id": None,
        "api_token_hash": None,
        "api_token_expiration": None,
        "created_at": datetime(2024, 3, 4, 12, 34, 57, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58, tzinfo=timezone.utc),
    }
    return User(**model_dict)


def test_get_job_404(
    test_client,
    test_db,
):
    """_summary_

    Args:
            test_db (_type_): _description_
    """
    print(test_db)  # => 1
    response = test_client.get("/jobs/e8a60c14-8838-46c9-816a-30191d6ab517")
    assert response.status_code == 404
    assert response.json() == {"message": "job not found with the given id"}


def test_get_jobs_simple(
    test_client,
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    # job of different owner's
    test_db.add(_get_model(3, should_change_owner_num=True))
    test_db.commit()

    response = test_client.get("/jobs")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    expect = [
        JobDef(
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
            submitted_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
        JobDef(
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
            submitted_at=datetime(2024, 3, 5, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_ignore_illegal_job(
    test_client,
    test_db,
):
    """_summary_
    Simple GET /jobs tests
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    # job3 has invalid job_info
    job_3 = _get_model(3)
    job_3.job_info = json.dumps({"dummy": ["dummy"]})
    test_db.add(job_3)
    test_db.commit()

    response = test_client.get("/jobs")
    adapter = TypeAdapter(List[JobDef])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert len(actual) == 2
    assert actual[0].job_id == "testjob1id"
    assert actual[1].job_id == "testjob2id"


def test_get_jobs_filtering_fields(
    test_client,
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get("/jobs?fields=job_id%2Cstatus%2Cname&order=ASC")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob1id",
            name="testjob1",
            status=JobStatus.submitted,
        ),
        GetJobsResponse(
            job_id="testjob2id",
            name="testjob2",
            status=JobStatus.submitted,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_all_fields(test_client, test_db):
    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    # This is the request sent from oqtopus-frontend
    response = test_client.get(
        "jobs?fields=job_id%2Cname%2Cdescription%2Cdevice_id%2Cjob_info%2Ctranspiler_info%2Csimulator_info%2Cmitigation_info%2Cjob_type%2Cshots%2Cstatus&page=1&size=20&order=DESC"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    assert response.status_code == 200
    assert len(actual) == 2


def test_get_jobs_invalid_fields(
    test_client,
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get("/jobs?fields=XXX%2Cstatus%2CYYY&order=ASC")
    actual = response.json()
    expect = json.loads(
        BadRequestResponse(message=f"fields {["XXX", "YYY"]} is invalid").body.decode()
    )

    assert response.status_code == 400
    assert actual == expect


def test_get_jobs_filtering_start_time(
    test_client,
    test_db,
):
    """_summary_
    filterling startime, expect only testjob2 will be got
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get(
        "/jobs?start_time=2024-03-05T07%3A04%3A24Z&order=ASC"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
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
            submitted_at=datetime(2024, 3, 5, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_filtering_end_time(
    test_client,
    test_db,
):
    """_summary_
    filterling end_time, expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get(
        "/jobs?end_time=2024-03-05T07%3A04%3A24Z&order=ASC"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
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
            submitted_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_filtering_start_time_uses_submitted_at_not_created_at(
    test_client,
    test_db,
):
    """
    start_time filter must use submitted_at.
    even if created_at is newer, older submitted_at job should be excluded.
    """

    test_db.flush()
    job1 = _get_model(1)
    job2 = _get_model(2)

    # Keep created_at after filter threshold for both jobs to detect wrong column usage.
    shared_created_at = datetime(2024, 3, 6, 12, 34, 56, tzinfo=timezone.utc)
    job1.created_at = shared_created_at
    job2.created_at = shared_created_at
    job1.submitted_at = datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc)
    job2.submitted_at = datetime(2024, 3, 5, 12, 34, 56, tzinfo=timezone.utc)

    test_db.add(job1)
    test_db.add(job2)
    test_db.commit()

    response = test_client.get(
        "/jobs?start_time=2024-03-05T07%3A04%3A24Z&order=ASC"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert [job.job_id for job in actual] == ["testjob2id"]


def test_get_jobs_by_status(test_client, test_db):
    """_summary_
    filtering by status, expect only testjob1 to be retrieved
    """
    test_db.flush()
    job1 = _get_model(1)
    job2 = _get_model(2)

    job1.status = JobStatus.ready
    job2.status = JobStatus.submitted

    test_db.add(job1)
    test_db.add(job2)
    test_db.commit()

    response = test_client.get(
        "/jobs?status=ready&order=ASC"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())

    assert response.status_code == 200
    assert [job.job_id for job in actual] == ["testjob1id"]


def test_get_jobs_filtering_search_string(
    test_client,
    test_db,
):
    """_summary_
    filterling search string "1", expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get("/jobs?q=1&order=ASC")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
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
            submitted_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_desc_order(
    test_client,
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = test_client.get("/jobs?order=DESC")
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
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
            submitted_at=datetime(2024, 3, 5, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
        GetJobsResponse(
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
            submitted_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc),
            ready_at=None,
            running_at=None,
            ended_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_pagination(
    test_client,
    test_db,
):
    """_summary_
    expect testjob2 and testjob1 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_model(i))
    test_db.commit()

    response = test_client.get("/jobs?page=3&size=3&fields=job_id")
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


def test_get_jobs_all_parameters(
    test_client,
    test_db,
):
    """_summary_
    filtering start_time, end_time, status, search string, and desc order, expect only testjob3 and testjob2 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_model(i))

    cancelledJob = _get_model(11)
    cancelledJob.status = JobStatus.cancelled
    cancelledJob.submitted_at = datetime(2024, 3, 5, 12, 34, 56, tzinfo=timezone.utc)
    test_db.add(cancelledJob)

    test_db.commit()

    response = test_client.get(
        "/jobs?fields=job_id%2Cdescription%2Cjob_info&start_time=2024-03-04T16%3A12%3A29Z&end_time=2024-03-08T16%3A12%3A29Z&status=submitted&q=test&order=DESC&page=2&size=2"
    )
    adapter = TypeAdapter(List[GetJobsResponse])
    actual = adapter.validate_python(response.json())
    expect = [
        GetJobsResponse(
            job_id="testjob3id",
            description="test job 3",
            job_info=JobInfo(program=["code"]),
        ),
        GetJobsResponse(
            job_id="testjob2id",
            description="test job 2",
            job_info=JobInfo(program=["code"]),
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_job_sortedness(test_client, test_db):
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
    test_db.add(_get_user_model(1))
    test_db.commit()
    job_ids: list[str] = []
    for n in range(1, 10):
        submit_resp = test_client.post("/jobs", content=mk_job(n).model_dump_json())
        print(f"submit_resp={submit_resp.json()}")
        job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
        job_ids.append(job_id)

    assert is_sorted(job_ids)


def test_get_jobs_handler(
    test_client,
    test_db,
):
    """_summary_

    Args:
            test_db (_type_): _description_
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    response = test_client.get("/jobs")
    assert response.status_code == 200

    adapter = TypeAdapter(List[JobDef])
    jobs = adapter.validate_python(response.json())

    expected = JobDef(
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
        submitted_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=timezone.utc),
        ready_at=None,
        running_at=None,
        ended_at=None,
    )
    assert jobs[0] == expected


def test_get_get(test_client, test_db):
    """_summary_
    Test for **the invariance of get and get**:
    retrieving jobs twice should have the same effect on the
    overall state as retrieving them once. In other words,
    the retrieval process must be idempotent.
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.commit()

    sql = select(Job).order_by(Job.created_at)

    resp1 = test_client.get(f"/jobs/{_get_model(1).id}")
    assert resp1.status_code == 200
    before_db = test_db.execute(sql).scalars().all()

    resp2 = test_client.get(f"/jobs/{_get_model(1).id}")
    assert resp2.status_code == 200
    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft


def test_submit_get(
    test_client,
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
    test_db.add(_get_user_model(1))
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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = test_client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = JobDef.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None


def test_submit_jobs_default_json_fields(test_client, test_db):
    """
    When transpiler_info, mitigation_info, and simulator_info are omitted from the request,
    the job saved to DB should have default value {} for each of those fields.
    """
    test_db.flush()
    test_db.add(_get_user_model(1))
    test_db.commit()

    body = SubmitJobRequest(
        name="submit-job-test",
        device_id="Kawasaki",
        job_type=JobType.sampling,
        job_info=SubmitJobInfo(program=["code"]),
        shots=1000,
    )

    submit_resp = test_client.post("/jobs", content=body.model_dump_json(exclude_none=True))
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id

    saved_job = test_db.get(Job, resp_job_id)
    assert json.loads(saved_job.transpiler_info) == {}
    assert json.loads(saved_job.mitigation_info) == {}
    assert json.loads(saved_job.simulator_info) == {}


def test_submit_cancel_delete(test_client, test_db):
    """_summary_
    Test for **the invariance of submit and delete**:
    submitting a job and then sequentially deleting it should result in no remaining effects."

    Args:
            test_db (_type_): _description_
    """
    sql = select(Job).order_by(Job.created_at)
    before_db = test_db.execute(sql).scalars().all()
    test_db.add(_get_user_model(1))
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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id

    # Deleting the job of reteurned job_id (Before deleting, canceling is required)
    cancel_resp = test_client.post(f"/jobs/{resp_job_id}/cancel")
    assert cancel_resp.status_code == 200

    # After cancelling, the same cancel request returs 200
    cancel_resp = test_client.post(f"/jobs/{resp_job_id}/cancel")
    assert cancel_resp.status_code == 200

    delete_resp = test_client.delete(f"/jobs/{resp_job_id}")
    assert delete_resp.status_code == 200

    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft


def test_submit_job_compat_error(test_client, test_db):
    """_summary_
    Test for **the invariance of submit and delete**:
    submitting a job and then sequentially deleting it should result in no remaining effects."

    Args:
            test_db (_type_): _description_
    """
    test_db.add(_get_user_model(1))
    test_db.commit()

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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 400


def test_can_submit_job_for_one_of_available_devices(test_client, test_db):
    """_summary_
    Test for checking submitting job for device that user is allowed to use
    """
    test_db.add(_get_user_model(1, available_devices=["Kawasaki", "SVSim"]))
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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = test_client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = JobDef.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None


def test_job_submit_for_device_user_cannot_access(test_client, test_db):
    """_summary_
    Test for checking submitting job for device that user is not allowed to use
    """
    test_db.add(_get_user_model(1, available_devices=["SC", "SVSim"]))
    test_db.commit()

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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 403
    assert submit_resp.json() == {"message": "cannot create job for device=Kawasaki"}


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


def test_get_sselog(test_client, test_db, test_storage):
    """_summary_
    Test for get sselog
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = b"log1"
    test_storage.put(key=f"testjob1id/{log_name}", data=log_body)

    # expected zip file with base64 encode
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w", compression=zipfile.ZIP_DEFLATED) as zip_data:
        zip_data.writestr(log_name, log_body)
    zip_stream.seek(0)
    zip_bin = zip_stream.read()
    zip_base64 = base64.b64encode(zip_bin).decode("utf-8")

    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    actual = adapter.validate_python(response.json())

    expect = {"file": zip_base64, "file_name": "oqtopus_test_sse_log_testjob1id.zip"}

    assert response.status_code == 200
    assert actual == expect

    # clean up
    test_storage.delete(key=f"testjob1id/{log_name}")


def test_get_sselog_invalid_owner(
    test_client,
    test_db,
    test_storage,
):
    """_summary_
    Test for get sselog when the job owner is invalid
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    job_model.owner = "user1"
    test_db.add(job_model)
    test_db.commit()

    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = b"log1"
    test_storage.put(key=f"testjob1id/{log_name}", data=log_body)

    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 404

    # clean up
    test_storage.delete(key=f"testjob1id/{log_name}")


def test_get_sselog_unknown_jobid(test_client, test_db, test_storage):
    """_summary_
    Test for get sselog when the job_id is invalid
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    job_model.id = "anotherjobid"
    test_db.add(job_model)
    test_db.commit()

    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = b"log1"
    test_storage.put(key=f"testjob1id/{log_name}", data=log_body)
    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 404

    # clean up
    test_storage.delete(key=f"testjob1id/{log_name}")


def test_get_sselog_invalid_jobtype(test_client, test_db, test_storage):
    """_summary_
    Test for get sselog when the job_type is not sse
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sampling
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = b"log1"
    test_storage.put(key=f"testjob1id/{log_name}", data=log_body)

    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 400

    # clean up
    test_storage.delete(key=f"testjob1id/{log_name}")


def test_get_sselog_running_job(test_client, test_db, test_storage):
    """_summary_
    Test for get sselog when the job status is neighter succeeded nor failed
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "running"
    test_db.add(job_model)
    test_db.commit()

    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    log_body = b"log1"
    test_storage.put(key=f"testjob1id/{log_name}", data=log_body)
    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())

    assert response.status_code == 400

    # clean up
    test_storage.delete(key=f"testjob1id/{log_name}")


def test_get_sselog_no_log(test_client, test_db, test_storage):
    """_summary_
    Test for get sselog when the job failed and there is no log file in S3
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "failed"
    test_db.add(job_model)
    test_db.commit()
    response = test_client.get("/jobs/testjob1id/sselog")
    adapter = TypeAdapter(dict[str, str])
    adapter.validate_python(response.json())
    assert response.status_code == 404


def test_put_user_program_to_s3(
    test_client,
    test_db,
    test_storage,
):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()
    test_db.add(_get_user_model(1))
    test_db.commit()
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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = test_client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = JobDef.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None

    program_data = test_storage.get(key=f"{resp_job_id}/oqtopus_test_program.py")
    assert program_data.decode() == "program1"


def test_put_user_program_to_s3_invalid_program(test_client, test_db):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()
    test_db.add(_get_user_model(1))
    test_db.commit()

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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 500


def test_put_user_program_to_s3_no_program(
    test_client,
    test_db,
):
    """_summary_
    Test for put user program to S3 when SSE
    """

    test_db.flush()
    test_db.add(_get_user_model(1))
    test_db.commit()

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
    submit_resp = test_client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 500


def test_delete_s3_folder(test_client, test_db, test_storage):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    test_storage.put(key="testjob1id/oqtopus_test_program.py", data=b"program1")
    test_storage.put(key="testjob1id/oqtopus_test_log.log", data=b"log1")
    test_storage.put(key="testjob2id/oqtopus_test_program.py", data=b"program2")
    test_storage.put(key="testjob2id/oqtopus_test_log.log", data=b"log2")

    # Request
    delete_resp = test_client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

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
    job = test_db.get(Job, "testjob1id")
    assert job is None


def test_delete_s3_folder_no_folder(test_client, test_db, test_storage):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    # Request
    delete_resp = test_client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    object_keys = [key for key in test_storage.prefix(prefix="testjob1id")]
    assert object_keys == []
    job = test_db.get(Job, "testjob1id")
    assert job is None


def test_delete_s3_folder_no_file(test_client, test_db, test_storage):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    test_storage.put(key="testjob1id/", data=b"program1")
    # Request
    delete_resp = test_client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    assert not test_storage.does_exist("testjob1id")
    job = test_db.get(Job, "testjob1id")
    assert job is None


def test_delete_s3_folder_folder_only(
    test_client,
    test_db,
    test_storage,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sse
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    test_storage.put(key="testjob1id/", data=b"program1")

    # Request
    delete_resp = test_client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    objects = test_storage.prefix(prefix="testjob1id")
    assert "Contents" not in objects
    job = test_db.get(Job, "testjob1id")
    assert job is None


def test_delete_s3_not_sse_job(
    test_client,
    test_db,
):
    """_summary_
    Test for delete s3 folder from S3 when SSE
    """

    test_db.flush()
    job_model = _get_model(1)
    job_model.job_type = JobType.sampling
    job_model.status = "succeeded"
    test_db.add(job_model)
    test_db.commit()

    # Request
    delete_resp = test_client.delete("/jobs/testjob1id")
    assert delete_resp.status_code == 200

    job = test_db.get(Job, "testjob1id")
    assert job is None
