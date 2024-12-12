import json
from datetime import datetime
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    ConflictErrorResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.provider.schemas.jobs import (
    GetJobsResponse,
    JobDef,
    JobInfo,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    UpdateJobInfoRequest,
    UpdateJobInfoResponse,
)
from sqlalchemy import Row, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

JobId = str


@router.get(
    "/jobs",
    response_model=list[Union[JobDef, GetJobsResponse]],
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_jobs(
    device_id: str,
    fields: Optional[str] = None,
    status: Optional[str] = None,
    max_results: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[Union[JobDef, GetJobsResponse]] | ErrorResponse:
    logger.info("invoked get_jobs")
    # Fields Control
    try:
        if fields is not None:
            fields_list = fields.split(",")
            MAP_SCHEMA_TO_MODEL = {v: k for k, v in MAP_MODEL_TO_SCHEMA.items()}
            converted_fields_list = [
                MAP_SCHEMA_TO_MODEL[field] for field in fields_list
            ]
            columns = [getattr(Job, field) for field in converted_fields_list]
            arg_select = columns
        else:
            arg_select = [Job]

        stmt = select(*arg_select).filter(Job.device_id == device_id)
        full_stmt = select(Job).filter(Job.device_id == device_id)
        # query = db.query(Job).filter(Job.device_id == device_id)
        # Filtering Jobs
        if status is not None:
            stmt = stmt.filter(Job.status == status)
            full_stmt = full_stmt.filter(Job.status == status)
        if timestamp is not None:
            time = datetime.fromisoformat(timestamp).astimezone(jst)
            stmt = stmt.filter(Job.created_at > time)
            full_stmt = full_stmt.filter(Job.created_at > time)
        if max_results is not None:
            stmt = stmt.limit(max_results)
            full_stmt = full_stmt.limit(max_results)

        if fields is None:
            # models is Job type
            models = db.scalars(stmt).all()
        else:
            # models is Row type
            models = db.execute(stmt).all()
        update_models = db.scalars(full_stmt).all()
        results: list[Union[JobDef, GetJobsResponse]] = []
        for model, update_model in zip(models, update_models):
            job = model_to_schema(model)
            if isinstance(job, ValueError):
                logger.warning(str(job))
            else:
                try:
                    if decode_job_status(update_model.status) == JobStatus.submitted:
                        update_model.status = JobStatus.ready
                        db.commit()
                        job.status = JobStatus(model.status)
                    results.append(job)
                except Exception as e:
                    logger.warning(str(job))
                    logger.warning(f"Error: {str(e)}")
        return results
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/jobs/{job_id}",
    response_model=JobDef,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> Union[JobDef, GetJobsResponse] | ErrorResponse:
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
    "/jobs/{job_id}",
    response_model=JobStatusUpdateResponse,
    responses={
        404: {"model": Detail},
        409: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def update_job(
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

        model.status = request.status
        db.commit()
        return JobStatusUpdateResponse(message="Job status updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{job_id}/job_info",
    response_model=UpdateJobInfoResponse,
    responses={
        400: {"model": Detail},
        404: {"model": Detail},
        500: {"model": Detail},
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
        job_info.transpiled_code = request.transpiled_code

        if request.result is not None:
            job_info.result = request.result
            job_info.reason = None
            return (JobStatus.succeeded, job_info)

        elif request.reason is not None:
            job_info.reason = request.reason
            job_info.result = None
            return (JobStatus.failed, job_info)

        return (None, job_info)

    if request.reason is not None and request.result is not None:
        return BadRequestResponse(
            detail="You cannot specify both a result and a reason."
        )

    try:
        stmt = select(Job).where(Job.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")
        (status, job_info) = patch_job_info(
            JobInfo.model_validate(json.loads(model.job_info))
        )
        model.job_info = JobInfo.model_dump_json(job_info)
        if status is not None:
            model.status = status
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
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def decode_job_status(s: str) -> JobStatus | ValueError:
    try:
        return JobStatus(s)
    except Exception as err:
        return ValueError(f"Failed to decode JobStatus: {str(err)}")


def model_to_schema(
    model: Union[Job, Row],
) -> Union[JobDef, GetJobsResponse] | ValueError:
    def decode_job_info(j: Any) -> JobInfo | ValueError:
        try:
            jobinfo = JobInfo.model_validate(j)
            return jobinfo
        except Exception as e:
            return ValueError(f"Failed to decode job_info: {str(e)}")

    if hasattr(model, "status"):
        status = decode_job_status(model.status)
    if hasattr(model, "job_info"):
        job_info = decode_job_info(json.loads(model.job_info))

    if type(model) is Job:
        if isinstance(job_info, ValueError):
            return job_info
        if isinstance(status, ValueError):
            return status
        return JobDef(
            job_id=model.id,
            name=model.name,
            description=model.description,
            device_id=model.device_id,
            shots=model.shots,
            job_info=job_info,
            status=status,
            transpiler_info=model.transpiler_info,
            mitigation_info=model.mitigation_info,
            simulator_info=model.simulator_info,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    elif type(model) is Row:
        dict_model = {}
        for k, v in model._mapping.items():
            if k == "id":
                dict_model["job_id"] = v
            elif k == "job_info":
                dict_model[k] = job_info
            elif k == "status":
                dict_model[k] = JobStatus(v)
            else:
                dict_model[k] = v
        return GetJobsResponse(**dict_model)
    else:
        return ValueError("Failed to decode model")
