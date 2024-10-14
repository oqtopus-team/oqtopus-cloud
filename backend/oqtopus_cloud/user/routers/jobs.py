import json

import uuid
from ast import literal_eval
from datetime import datetime
from typing import Any, Literal, Optional, Tuple

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi import Request as Event
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
)
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.model_util import model_to_schema_dict
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.jobs import GetJobStatusResponse
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse
from oqtopus_cloud.user.schemas.jobs import SubmitJobResponse, JobId, JobStatus, JobDef

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
        # TODO: get_jobsでの詰替え
        # 外向け（for UI）と内部（for edge）でデータの出し分けをした方がよい
        return [model_to_schema(job) for job in jobs]
        # for job in jobs:
        #     logger.info(f"job: {job.device_id}")
        #     #yield model_to_schema(job)

        # return None
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
    request: JobDef,
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
            # TODO: UUIDv7
            id=uuid.uuid4(),
            owner=owner,
            name=name,
            description=description,
            device_id=request.device_id,
            job_info=request.job_info,
            transpiler_info=request.transpiler_info,
            simulator_info=request.simulator_info,
            mitigation_info=request.mitigation_info,
            job_type=request.job_type,
            shots=shots,
            created_at=datetime.now(),
        )
        db.add(job)
        db.commit()
        return SubmitJobResponse(job_id=JobId(job.id))
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
        job = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job is None:
            return NotFoundErrorResponse(detail="job not found with the given id")
        return model_to_schema(job)
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
    return GetJobStatusResponse(job_id=JobId(job_id), status=JobStatus(job.status))


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
            job.status = "cancelled"
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
