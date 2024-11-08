import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from oqtopus_cloud.common.model_util import model_to_schema_dict
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.provider.schemas.jobs import (
    JobDef,
    JobInfo,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

JobId = str


@router.get(
    "/jobs",
    response_model=list[JobDef],
)
@tracer.capture_method
def get_jobs(
    device_id: str,
    status: Optional[str] = None,
    max_results: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[JobDef]:
    logger.info("invoked get_jobs")
    query = db.query(Job).filter(Job.device_id == device_id)
    if status is not None:
        query = query.filter(Job.status == status)
    if timestamp is not None:
        time = datetime.fromisoformat(timestamp).astimezone(jst)
        query = query.filter(Job.created_at > time)
    if max_results is not None:
        query = query.limit(max_results)
    models = query.all()
    jobs: list[JobDef] = []
    for model in models:
        job = model_to_schema(model)
        if job is not None:
            jobs.append(job)
    return jobs


@router.get(
    "/jobs/{job_id}",
    response_model=JobId,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobId | ErrorResponse:
    logger.info("invoked get_job")
    try:
        job = db.get(Job, job_id)
        if job is None:
            return NotFoundErrorResponse("Job not found")
        return job.id
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{job_id}",
    response_model=JobStatusUpdateResponse,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def update_job(
    job_id: str,
    request: JobStatusUpdate,
    db: Session = Depends(get_db),
) -> JobStatusUpdateResponse | ErrorResponse:
    logger.info("invoked get_job")
    try:
        job = (
            db.query(Job)
            .filter(
                Job.id == job_id, or_(Job.status == "ready", Job.status == "running")
            )
            .first()
        )
        if job is None:
            return NotFoundErrorResponse("Job not found")
        if request.status is not None:
            job.status = request.status  # type: ignore
        db.commit()
        return JobStatusUpdateResponse(message="Job status updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


MAP_MODEL_TO_SCHEMA = {
    "id": "id",
    "owner": "owner",
    "status": "status",
    "name": "name",
    "description": "description",
    "device_id": "device_id",
    "job_info": "job_info",
    "transpiler_info": "transpiler_info",
    "simulator_info": "simulator_info",
    "mitigation_info": "mitigation_info",
    "job_type": "job_type",
    "shots": "shots",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def model_to_schema(model: Job) -> JobDef | None:
    def decode_job_info(j: Any) -> JobInfo | None:
        try:
            return JobInfo.model_validate(j)
        except Exception as _:
            return None

    job_info = decode_job_info(json.loads(model.job_info))
    if job_info is None:
        return None

    return JobDef(
        job_id=model.id,
        name=model.name,
        description=model.description,
        device_id=model.device_id,
        shots=model.shots,
        job_info=job_info,
        status=JobStatus(model.status),
        transpiler_info=model.transpiler_info,
        mitigation_info=model.mitigation_info,
        simulator_info=model.simulator_info,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
