import json
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
)

# from uuid_extensions import uuid7
from uuid_v7.base import uuid7
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.jobs import (
    GetJobStatusResponse,
    JobDef,
    JobInfo,
    JobStatus,
    JobType,
    SubmitJobRequest,
    SubmitJobResponse,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse

from . import LoggerRouteHandler

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


class BadRequest(Exception):
    def __init__(self, detail: str):
        self.detail = detail


@router.get(
    "/jobs",
    response_model=list[JobDef],
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_jobs(
    event: Event,
    db: Session = Depends(get_db),
) -> list[JobDef] | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        stmt = select(Job).filter(Job.owner == owner).order_by(Job.created_at)
        jobs = db.scalars(stmt).all()
        results: list[JobDef] = []
        for job_model, job in [(job, model_to_schema(job)) for job in jobs]:
            if job is None:
                logger.warning(f"Failed to encode job model to schema: {job_model.id}")
            else:
                results.append(job)
        return results

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


def validate_name(request: JobDef) -> str | None:
    if request.name is not None:
        return request.name
    return ""


def validate_description(
    request: JobDef,
) -> str | None:
    return request.description if (request.description is not None) else ""


@router.post(
    "/jobs",
    response_model=SubmitJobResponse,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def submit_jobs(
    event: Event,
    request: SubmitJobRequest,
    db: Session = Depends(get_db),
) -> SubmitJobResponse | ErrorResponse:
    try:
        device = db.get(Device, request.device_id)  # type: ignore
        if device is None:
            return BadRequestResponse(detail="device not found")
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        if device.status != "available":
            return BadRequestResponse(f"device {device.id} is not available")

        # NOTE: method and operator is validated by pydantic
        shots = request.shots
        # name is optional
        name = validate_name(request)

        # description is optional
        description = validate_description(request)

        job = Job(
            # id=uuid7(as_type="str"),
            id=str(uuid7()),
            owner=owner,
            name=name,
            description=description,
            device_id=request.device_id,
            job_info=json.dumps({"desc": request.job_info.model_dump()}),
            transpiler_info=request.transpiler_info,
            simulator_info=request.simulator_info,
            mitigation_info=request.mitigation_info,
            job_type=request.job_info.job_type,
            shots=shots,
            created_at=datetime.now(),
        )
        db.add(job)
        db.commit()
        return SubmitJobResponse(job_id=job.id)
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/jobs/{job_id}",
    response_model=JobDef,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_job(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> JobDef | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner, "job_id": job_id})
        job_model = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job_model is None:
            return NotFoundErrorResponse(detail="job not found with the given id")
        job = model_to_schema(job_model)
        if job is None:
            logger.warning("warn: Failed to encode job model to schema.")
            return NotFoundErrorResponse(detail="job not found with the given id")
        return job
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.delete(
    "/jobs/{job_id}",
    response_model=SuccessResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def delete_job(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        job = db.get(Job, job_id)

        if job is None:
            return NotFoundErrorResponse(detail="job not found with the given id")

        if job.owner != owner or job.status not in ["success", "failed", "cancelled"]:
            return NotFoundErrorResponse(
                detail=f"{job_id} job is not in valid status for deletion (valid statuses for deletion: 'success', 'failed' and 'cancelled')"
            )

        db.delete(job)
        db.commit()
        return SuccessResponse(message="job deleted")
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/jobs/{job_id}/status",
    response_model=GetJobStatusResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_job_status(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> GetJobStatusResponse | ErrorResponse:
    owner = event.state.owner
    logger.info("invoked!", extra={"owner": owner})
    job = (
        db.query(Job.id, Job.status)
        .filter(
            Job.id == job_id,
            Job.owner == owner,
        )
        .first()
    )
    if job is None:
        return NotFoundErrorResponse(detail="job not found with the given id")
    return GetJobStatusResponse(job_id=job_id, status=job.status)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=SuccessResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def cancel_job(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        job = db.get(Job, job_id)

        if job is None:
            return NotFoundErrorResponse(detail="job not found with the given id")
        if job.owner != owner or job.status not in ["ready", "submitted", "running"]:
            return NotFoundErrorResponse(
                detail=f"{job_id} job is not in valid status for cancellation (valid statuses for cancellation: 'ready', 'submitted' and 'running')"
            )
        if job.status in ["submitted", "ready", "running"]:
            logger.info(
                "job is in submitted or ready or running state, so it will be marked as cancelling"
            )
            job.status = JobStatus.cancelled
            db.commit()
        return SuccessResponse(message="cancel request accepted")
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


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


def decode_job_info(j: Any) -> JobInfo | None:
    try:
        return JobInfo.model_validate(j)
    except Exception as _:
        return None


def model_to_schema(model: Job) -> JobDef | None:
    job_info = decode_job_info(json.loads(model.job_info))
    if job_info is None:
        return None

    return JobDef(
        job_id=model.id,
        name=model.name,
        description=model.description,
        device_id=model.device_id,
        shots=model.shots,
        job_type=JobType(job_info.desc.job_type),
        job_info=job_info,
        status=JobStatus(model.status),
        transpiler_info=model.transpiler_info,
        mitigation_info=model.mitigation_info,
        simulator_info=model.simulator_info,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
