import json
from datetime import datetime
from typing import List

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.user.lambda_function import app

# from oqtopus_cloud.user.routers.jobs import (
#     get_job,
#     get_job_status,
#     get_jobs,
#     model_to_schema,
# )
from oqtopus_cloud.user.schemas.jobs import (
    JobDef,
    JobInfo,
    JobInfoSampling,
    JobStatus,
    JobType,
    SubmitJobRequest,
    SubmitJobResponse,
)
from pydantic.type_adapter import TypeAdapter
from sqlalchemy import select

client = TestClient(app)


def _get_model() -> Job:
    mode_dict = {
        "id": "testjob1id",
        "owner": "admin",
        "name": "testjob1",
        "description": "test job 1",
        "device_id": "Kawasaki",
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
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Job(**mode_dict)


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
    assert response.json() == {"detail": "job not found with the given id"}


def test_get_jobs_handler(
    test_db,
):
    """_summary_

    Args:
            test_db (_type_): _description_
    """

    test_db.flush()
    test_db.add(_get_model())
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
        job_info=JobInfo(
            desc=JobInfoSampling(job_type="sampling", code="code"),
        ),
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
    test_db.add(_get_model())
    test_db.commit()

    sql = select(Job).order_by(Job.created_at)

    resp1 = client.get(f"/jobs/{_get_model().id}")
    assert resp1.status_code == 200
    before_db = test_db.execute(sql).scalars().all()

    resp2 = client.get(f"/jobs/{_get_model().id}")
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
        job_info=JobInfoSampling(job_type="sampling", code="codecodecode"),
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
    assert resp_job.job_info.desc == body.job_info


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
        job_info=JobInfoSampling(job_type="sampling", code="codecodecode"),
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
