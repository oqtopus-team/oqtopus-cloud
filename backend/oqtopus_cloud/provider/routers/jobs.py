import uuid
from ast import literal_eval
from datetime import datetime
from typing import Optional

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
    JobId,
    JobDef,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    UnfetchedJobsResponse,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")


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
    jobs = query.all()
    return [model_to_schema(job) for job in jobs]


@router.get(
    "/jobs/unfetched",
    response_model=UnfetchedJobsResponse,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_unfetched_jobs(
    device_id: str,
    status: str,
    max_results: Optional[int] = None,
    db: Session = Depends(get_db),
) -> UnfetchedJobsResponse | ErrorResponse:
    logger.info("invoked get_job")
    try:
        if status not in ["submitted", "cancelling"]:
            return BadRequestResponse("Invalid status")
        if status == "submitted":
            query = (
                db.query(Job)
                .filter(Job.device_id == device_id, Job.status == "submitted")
                .order_by(Job.created_at)
            )
            update_status = "ready"
        else:
            query = (
                db.query(Job)
                .filter(Job.device_id == device_id)
                .order_by(Job.created_at)
            )
            update_status = "cancelled"

        if max_results is not None:
            query = query.limit(max_results)

        jobs = query.all()
        if len(jobs) != 0:
            for job in jobs:
                job.status = update_status  # type: ignore
            db.commit()
        job_ids = [JobId(job.id) for job in jobs]
        return UnfetchedJobsResponse(root=job_ids)  # type: ignore
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


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
    "status": "status",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def model_to_schema(model: Job) -> JobDef:
    schema_dict = model_to_schema_dict(model, MAP_MODEL_TO_SCHEMA)

    # load as json if not None.
    # if schema_dict["basis_gates"]:
    #     schema_dict["basis_gates"] = json.loads(schema_dict["basis_gates"])
    # logger.info("schema_dict!!!:", schema_dict)
    if schema_dict["created_at"]:
        schema_dict["created_at"] = schema_dict["created_at"].astimezone(jst)
    if schema_dict["updated_at"]:
        schema_dict["updated_at"] = schema_dict["updated_at"].astimezone(jst)

    response = JobDef(**schema_dict)
    return response
