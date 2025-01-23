import json
from datetime import datetime
from typing import List

from fastapi.testclient import TestClient
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
    GetJobsResponse,
    JobDef,
    JobInfo,
    JobStatus,
    JobType,
    SubmitJobInfo,
    SubmitJobRequest,
    SubmitJobResponse,
)
from pydantic.type_adapter import TypeAdapter
from sqlalchemy import select

client = TestClient(app)


def _get_model(n: int) -> Job:
    model_dict = {
        "id": f"testjob{n}id",
        "owner": "admin",
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
        "created_at": datetime(2024, 3, 3 + n, 12, 34, 56),
    }
    return Job(**model_dict)


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
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs")
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
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 4, 12, 34, 56),
            updated_at=None,
        ),
        JobDef(
            job_id="testjob2id",
            name="testjob2",
            description="test job 2",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(program=["code"]),
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 5, 12, 34, 56),
            updated_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_filtering_fields(
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs?fields=job_id%2Cstatus%2Cname&order=ASC")
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


def test_get_jobs_invalid_fields(
    test_db,
):
    """_summary_
    GET job_id, status and name by ASC order
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
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


def test_get_jobs_filtering_startTime(
    test_db,
):
    """_summary_
    filterling startime, expect only testjob2 will be got
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs?startTime=2024-03-05T07%3A04%3A24%2B09%3A00&order=ASC")
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
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 5, 12, 34, 56),
            updated_at=None,
        ),
    ]

    assert response.status_code == 200
    assert actual == expect


def test_get_jobs_filtering_endTime(
    test_db,
):
    """_summary_
    filterling endtime, expect only testjob1 will be got
    """

    test_db.flush()
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs?endTime=2024-03-05T07%3A04%3A24%2B09%3A00&order=ASC")
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
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 4, 12, 34, 56),
            updated_at=None,
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
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs?q=1&order=ASC")
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
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 4, 12, 34, 56),
            updated_at=None,
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
    test_db.add(_get_model(1))
    test_db.add(_get_model(2))
    test_db.commit()

    response = client.get("/jobs?order=DESC")
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
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 5, 12, 34, 56),
            updated_at=None,
        ),
        GetJobsResponse(
            job_id="testjob1id",
            name="testjob1",
            description="test job 1",
            device_id="Kawasaki",
            job_type=JobType.sampling,
            job_info=JobInfo(program=["code"]),
            transpiler_info=json.dumps({"this_is": "transpiler_info"}),
            simulator_info=json.dumps({"this_is": "simulator_info"}),
            mitigation_info=json.dumps(
                {"field1": "value1", "field2": "value2", "field3": "value3"}
            ),
            status=JobStatus.submitted,
            shots=1000,
            created_at=datetime(2024, 3, 4, 12, 34, 56),
            updated_at=None,
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
        test_db.add(_get_model(i))
    test_db.commit()

    response = client.get("/jobs?page=3&size=3&fields=job_id")
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
    test_db,
):
    """_summary_
    filtering starttime, endtime, search string, and desc order, expect only testjob3 and testjob2 will be got in this order
    """

    test_db.flush()
    for i in range(1, 10):
        test_db.add(_get_model(i))
    test_db.commit()

    response = client.get(
        "/jobs?fields=job_id%2Cdescription%2Cjob_info&startTime=2024-03-04T16%3A12%3A29%2B09%3A00&endTime=2024-03-08T16%3A12%3A29%2B09%3A00&q=test&order=DESC&page=2&size=2"
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


def test_job_sortedness(test_db):
    def mk_job(n: int) -> SubmitJobRequest:
        return SubmitJobRequest(
            name=f"test-job-{n}",
            device_id="Kawasaki",
            status=JobStatus.submitted,
            job_type=JobType.sampling,
            job_info=SubmitJobInfo(program=["code"]),
            simulator_info="{}",
            transpiler_info="{}",
            mitigation_info="{}",
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
    test_db.add(_get_model(1))
    test_db.commit()

    response = client.get("/jobs")
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
        transpiler_info=json.dumps({"this_is": "transpiler_info"}),
        simulator_info=json.dumps({"this_is": "simulator_info"}),
        mitigation_info=json.dumps(
            {
                "field1": "value1",
                "field2": "value2",
                "field3": "value3",
            }
        ),
        status=JobStatus.submitted,
        shots=1000,
        created_at=datetime(2024, 3, 4, 12, 34, 56),
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
    test_db.add(_get_model(1))
    test_db.commit()

    sql = select(Job).order_by(Job.created_at)

    resp1 = client.get(f"/jobs/{_get_model(1).id}")
    assert resp1.status_code == 200
    before_db = test_db.execute(sql).scalars().all()

    resp2 = client.get(f"/jobs/{_get_model(1).id}")
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
        mitigation_info=json.dumps(
            {
                "field1": "value1",
                "field2": {
                    "subfield1": "value2",
                    "subfield2": ["value3", 42, True],
                },
            }
        ),
        simulator_info='"This is simulator info"',
        transpiler_info="{}",
        shots=1024,
        status=JobStatus.submitted,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id
    # Getting the job of reteurned job_id
    get_resp = client.get(f"/jobs/{resp_job_id}")
    assert get_resp.status_code == 200
    resp_job = JobDef.model_validate(get_resp.json())
    # And these jobs should be same.
    assert resp_job.name == body.name
    assert resp_job.description == body.description
    assert resp_job.job_type == body.job_type
    assert resp_job.job_info.program == body.job_info.program
    assert resp_job.job_info.result is None


def test_submit_delete(test_db):
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
        mitigation_info=json.dumps(
            {
                "field1": "value1",
                "field2": {
                    "subfield1": "value2",
                    "subfield2": ["value3", 42, True],
                },
            }
        ),
        simulator_info='"This is simulator info"',
        transpiler_info="{}",
        shots=1024,
        status=JobStatus.running,
    )

    # Submitting
    submit_resp = client.post("/jobs", content=body.model_dump_json())
    assert submit_resp.status_code == 200
    resp_job_id = SubmitJobResponse.model_validate(submit_resp.json()).job_id

    # Deleting the job of reteurned job_id (Before deleting, canceling is required)
    cancel_resp = client.post(f"/jobs/{resp_job_id}/cancel")
    assert cancel_resp.status_code == 200
    delete_resp = client.delete(f"/jobs/{resp_job_id}")
    assert delete_resp.status_code == 200

    after_db = test_db.execute(sql).scalars().all()

    # Aftet the work, the whole state of the DB should not be changed.
    assert len(before_db) == len(after_db)
    for bef, aft in zip(before_db, after_db):
        assert bef == aft
