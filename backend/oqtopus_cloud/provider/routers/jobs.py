import uuid
from ast import literal_eval
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
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
    response_model=list[JobId],
)
@tracer.capture_method
def get_jobs(
    device_id: str,
    status: Optional[str] = None,
    max_results: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[Job]:
    logger.info("invoked get_jobs")
    query = db.query(Job).filter(Job.device == device_id)
    if status is not None:
        query = query.filter(Job.status == status)
    if timestamp is not None:
        time = datetime.fromisoformat(timestamp).astimezone(jst)
        query = query.filter(Job.created_at > time)
    if max_results is not None:
        query = query.limit(max_results)
    jobs = query.all()
    return jobs


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
                .filter(Job.device == device_id, Job.status == "submitted")
                .order_by(Job.created_at)
            )
            update_status = "ready"
        else:
            query = (
                db.query(Job).filter(Job.device == device_id).order_by(Job.created_at)
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
    "/jobs/{jobId}",
    response_model=JobId,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_job(
    jobId: str,
    db: Session = Depends(get_db),
) -> JobId | ErrorResponse:
    logger.info("invoked get_job")
    try:
        id = uuid.UUID(jobId).bytes
    except Exception:
        return BadRequestResponse("Invalid jobId")
    try:
        job = db.get(Job, id)
        if job is None:
            return NotFoundErrorResponse("Job not found")
        return job.id
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{jobId}",
    response_model=JobStatusUpdateResponse,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def update_job(
    jobId: str,
    request: JobStatusUpdate,
    db: Session = Depends(get_db),
) -> JobStatusUpdateResponse | ErrorResponse:
    logger.info("invoked get_job")
    try:
        id = uuid.UUID(jobId).bytes
    except Exception:
        return BadRequestResponse("Invalid jobId")
    try:
        job = (
            db.query(Job)
            .filter(Job.id == id, or_(Job.status == "ready", Job.status == "running"))
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
