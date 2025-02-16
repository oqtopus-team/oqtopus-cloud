import json
from datetime import datetime
from typing import Any, Optional

import pytz
from fastapi import APIRouter, Depends
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    ConflictErrorResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.provider.schemas.jobs import (
    JobDef,
    JobInfo,
    JobResult,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    JobType,
    UpdateJobInfoRequest,
    UpdateJobInfoResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

JobId = str


@router.get(
    "/jobs",
    response_model=list[JobDef],
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_jobs(
    device_id: str,
    fields: Optional[str] = None,
    status: Optional[str] = None,
    max_results: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[JobDef] | ErrorResponse:
    logger.info("invoked get_jobs")
    try:
        # Fields Control
        fields_list = None
        if fields is not None:
            fields_list = fields.split(",")
            valid_fields_list = [field in JobDef.model_fields for field in fields_list]
            if all(valid_fields_list):
                MAP_SCHEMA_TO_MODEL = {v: k for k, v in MAP_MODEL_TO_SCHEMA.items()}
                converted_fields_list = [
                    MAP_SCHEMA_TO_MODEL[field] for field in fields_list
                ]
                columns = [getattr(Job, field) for field in converted_fields_list]

                # remove duplicated fields
                arg_select = list(dict.fromkeys(columns))
                select_stmt = (
                    select(Job)
                    .filter(Job.device_id == device_id)
                    .options(load_only(*arg_select))
                )
            else:
                invalid_indices = [
                    i for i, field in enumerate(valid_fields_list) if field is False
                ]
                invalid_fields_list = [fields_list[i] for i in invalid_indices]
                return InternalServerErrorResponse(
                    message=f"fields {invalid_fields_list} is invalid"
                )
        else:
            select_stmt = select(Job).filter(Job.device_id == device_id)

        # Filtering Jobs
        if status is not None:
            select_stmt = select_stmt.filter(Job.status == status)
        if timestamp is not None:
            time = datetime.fromisoformat(timestamp).astimezone(jst)
            select_stmt = select_stmt.filter(Job.created_at > time)
        if max_results is not None:
            select_stmt = select_stmt.limit(max_results)

        models = db.scalars(select_stmt).all()

        results: list[JobDef] = []
        # for model, update_status in zip(models, update_statuses):
        for model in models:
            job = model_to_schema(model, fields_list)
            if isinstance(job, ValueError):
                logger.warning(str(job))
                return NotFoundErrorResponse("Job not found")
            else:
                # if status is "submitted", then update status to "ready"
                if decode_job_status(model.status) == JobStatus.submitted:
                    set_job_status(model, JobStatus.ready)
                # checking model objects has status attribute
                if (fields is None) or (fields is not None and "status" in fields):
                    job.status = JobStatus(model.status)
                results.append(job)
        db.commit()
        return results
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/jobs/{job_id}",
    response_model=JobDef,
    responses={
        404: {"model": Message},
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobDef | ErrorResponse:
    logger.info("invoked get_job")
    try:
        model = db.get(Job, job_id)
        if model is None:
            return NotFoundErrorResponse("Job not found")
        job = model_to_schema(model)
        if isinstance(job, ValueError):
            logger.warning(str(job))
            return NotFoundErrorResponse("Job not found")
        else:
            return job
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{job_id}/status",
    response_model=JobStatusUpdateResponse,
    responses={
        404: {"model": Message},
        409: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_job_status(
    job_id: str,
    request: JobStatusUpdate,
    db: Session = Depends(get_db),
) -> JobStatusUpdateResponse | ErrorResponse:
    logger.info("invoked get_job")
    try:
        stmt = select(Job).where(Job.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")

        if decode_job_status(model.status) != JobStatus.ready:
            return ConflictErrorResponse(
                f"The specified job is not a status that allows transition to the status {request.status}"
            )

        set_job_status(model, request.status)
        db.commit()
        return JobStatusUpdateResponse(message="Job status updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{job_id}/job_info",
    response_model=UpdateJobInfoResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_job_info(
    job_id: str,
    request: UpdateJobInfoRequest,
    db: Session = Depends(get_db),
) -> UpdateJobInfoResponse | ErrorResponse:
    logger.info("invoked: update_job_info")
    logger.info(
        f"with parameters: job_id={job_id}, request={request.model_dump_json()}"
    )

    def patch_job_info(job_info: JobInfo) -> tuple[Optional[JobStatus], JobInfo]:
        status = request.overwrite_status
        incoming = request.job_info
        if incoming is None:
            return (status, job_info)

        if incoming.transpiled_program is not None:
            job_info.transpiled_program = incoming.transpiled_program

        if incoming.result is not None:
            job_info.result = incoming.result
            if status is None:
                status = JobStatus.succeeded

        if incoming.message is not None:
            job_info.message = incoming.message

        return (status, job_info)

    try:
        stmt = select(Job).where(Job.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")
        job_info = JobInfo.model_validate(json.loads(model.job_info))

        # The job result must be compatible with the job info.
        if (
            request.job_info is not None
            and request.job_info.result is not None
            and model.job_type != jobtype_of_result(request.job_info.result)
        ):
            return BadRequestResponse(
                message="The job result type is not compatible with job info."
            )

        # Calculate upodated job_info.
        (status, job_info) = patch_job_info(job_info)

        # Validate the consitency of patched job_info and status
        if (
            # Job with non-null result should be succeeded
            (job_info.result is not None and status != JobStatus.succeeded)
            # Job cannot go back to status of submitted or ready.
            or status in [JobStatus.submitted, JobStatus.ready]
        ):
            return BadRequestResponse(
                message="The overwritten status and job_info is inconsistent"
            )

        model.job_info = JobInfo.model_dump_json(job_info)
        if status is not None:
            set_job_status(model, status)
        db.commit()
        return UpdateJobInfoResponse(message="Job info updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


# TODO: match parameter names of model and schema
MAP_MODEL_TO_SCHEMA = {
    "id": "job_id",
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
    "execution_time": "execution_time",
    "submitted_at": "submitted_at",
    "ready_at": "ready_at",
    "running_at": "running_at",
    "ended_at": "ended_at",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def jobtype_of_result(r: JobResult) -> JobType | None:
    if r.counts is not None:
        return JobType.sampling
    elif r.estimation is not None:
        return JobType.estimation
    return None


def decode_job_status(s: str) -> JobStatus | ValueError:
    try:
        return JobStatus(s)
    except Exception as err:
        return ValueError(f"Failed to decode JobStatus: {str(err)}")


def decode_job_info(j: Any) -> JobInfo | ValueError:
    try:
        jobinfo = JobInfo.model_validate(j)
        return jobinfo
    except Exception as e:
        return ValueError(f"Failed to decode job_info: {str(e)}")


def parse_job_type(jt: str) -> JobType | ValueError:
    try:
        return JobType(jt)
    except Exception:
        return ValueError(f"{jt} is not a valid JobType")


def localize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return pytz.utc.localize(dt)


def is_datetime_field(fld: str) -> bool:
    if fld == "submitted_at":
        return True
    elif fld == "ready_at":
        return True
    elif fld == "running_at":
        return True
    elif fld == "ended_at":
        return True
    elif fld == "created_at":
        return True
    elif fld == "updated_at":
        return True

    return False

def set_job_status(model: Job, status: str | JobStatus) -> None:
    if isinstance(status, str):
        status = JobStatus(status)

    model.status = status
    if status == JobStatus.ready:
        if model.ready_at is None:
            model.ready_at = datetime.now()
    elif status == JobStatus.running:
        if model.running_at is None:
            model.running_at = datetime.now()
    elif (
        status == JobStatus.succeeded
        or status == JobStatus.failed
        or status == JobStatus.cancelled
    ):
        if model.ended_at is None:
            model.ended_at = datetime.now()
    return

def model_to_schema(
    model: Job, fields: Optional[list[str]] = None
) -> JobDef | ValueError:
    status = decode_job_status(model.status)
    if isinstance(status, ValueError):
        return status
    job_info = decode_job_info(json.loads(model.job_info))
    if isinstance(job_info, ValueError):
        return job_info
    job_type = parse_job_type(str(model.job_type))
    if isinstance(job_type, ValueError):
        return job_type
    return JobDef(
        job_id=model.id,
        name=model.name,
        description=model.description,
        device_id=model.device_id,
        shots=model.shots,
        job_type=job_type,
        job_info=job_info,
        status=status,
        transpiler_info=model.transpiler_info,
        mitigation_info=model.mitigation_info,
        simulator_info=model.simulator_info,
        execution_time=model.execution_time,
        submitted_at=localize(model.submitted_at),
        ready_at=localize(model.ready_at),
        running_at=localize(model.running_at),
        ended_at=localize(model.ended_at),
        created_at=pytz.utc.localize(model.created_at),
        updated_at=localize(model.updated_at),
    )
