import json
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from oqtopus_cloud.common.models.job import Job as JobModel
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import (
    JOB_INFO_INPUT_PARAM,
    JOB_INFO_COMBINED_PROGRAM_PARAM,
    JOB_INFO_TRANSPILE_RESULT_PARAM,
    JOB_INFO_RESULT_PARAM,
    JOB_INFO_SSE_LOG_PARAM,
)
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
    Job,
    JobDef,
    JobInfoUploadPresignedURL,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    JobType,
    UpdateJobTranspilerInfoRequest,
    UpdateJobTranspilerInfoResponse,
)
from sqlalchemy import asc, select
from sqlalchemy.orm import Session, load_only
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")

JobId = str

s3_key_pattern = r"^(?P<id>[\w-]+)/(?P<name>input|combined_program|result|transpile_result|sse_log)\.zip$"


@router.get(
    "/jobs",
    response_model=list[Job],
    response_model_exclude_none=True,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_jobs(
    device_id: str,
    fields: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> list[Job] | ErrorResponse:
    logger.info("invoked get_jobs")
    try:
        select_stmt = select(JobModel).filter(
            JobModel.device_id == device_id, JobModel.status != "registered"
        )

        # Fields Control
        fields_list = None
        if fields is not None:
            fields_list = fields.split(",")
            valid_fields_list = [field in Job.model_fields for field in fields_list]
            if all(valid_fields_list):
                converted_fields_list = [
                    MAP_SCHEMA_TO_MODEL[field]
                    for field in fields_list
                    if field in MAP_SCHEMA_TO_MODEL
                ]
                arg_select = [
                    getattr(JobModel, field) for field in converted_fields_list
                ]

                # remove duplicated fields
                arg_select = list(dict.fromkeys(arg_select))

                if arg_select:
                    select_stmt = select_stmt.options(load_only(*arg_select))
            else:
                invalid_indices = [
                    i for i, field in enumerate(valid_fields_list) if field is False
                ]
                invalid_fields_list = [fields_list[i] for i in invalid_indices]
                return BadRequestResponse(
                    message=f"fields {invalid_fields_list} is invalid"
                )

        select_stmt = select_stmt.order_by(asc(JobModel.submitted_at), asc(JobModel.id))

        # Filtering Jobs
        if status is not None:
            select_stmt = select_stmt.filter(JobModel.status == status)
        if timestamp is not None:
            time = datetime.fromisoformat(timestamp).astimezone(utc)
            select_stmt = select_stmt.filter(JobModel.created_at > time)
        if limit is not None:
            select_stmt = select_stmt.limit(limit)

        models = db.scalars(select_stmt).all()

        results: list[Job] = []
        # for model, update_status in zip(models, update_statuses):
        for model in models:
            job = model_to_filtered_schema(model, storage, fields_list)
            if isinstance(job, ValueError):
                logger.warning(str(job))
                # ignore illegal jobs
                continue
            else:
                # if status is "submitted", then update status to "ready"
                if parse_job_status(model.status) == JobStatus.submitted:
                    set_job_status(model, JobStatus.ready)
                # checking model objects has status attribute
                if (fields is None) or (fields is not None and "status" in fields):
                    job.status = JobStatus(model.status)
                results.append(job)
        db.commit()
        return results
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/jobs/{job_id}",
    response_model=JobDef,
    response_model_exclude_none=True,
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
    storage: AbstractStorage = Depends(get_storage),
) -> JobDef | ErrorResponse:
    logger.info("invoked get_job")
    try:
        model = db.get(JobModel, job_id)
        if model is None:
            return NotFoundErrorResponse("Job not found")
        job = model_to_schema(model, storage)
        if isinstance(job, ValueError):
            logger.warning(str(job))
            return NotFoundErrorResponse("Job not found")
        else:
            return job
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/jobs/{job_id}/upload",
    response_model=list[JobInfoUploadPresignedURL],
    responses={
        404: {"model": Message},
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_upload(
    job_id: str,
    items: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> list[JobInfoUploadPresignedURL] | ErrorResponse:
    logger.info("invoked get_job")
    try:
        model = db.get(JobModel, job_id)
        if model is None:
            return NotFoundErrorResponse("Job not found")

        items_list = items.split(",")
        diff = set(items_list).difference(
            {
                JOB_INFO_COMBINED_PROGRAM_PARAM,
                JOB_INFO_TRANSPILE_RESULT_PARAM,
                JOB_INFO_RESULT_PARAM,
                JOB_INFO_SSE_LOG_PARAM,
            }
        )
        if diff:
            return BadRequestResponse(f"Unsupported item(s) for upload: {list(diff)}")

        if (
            JOB_INFO_COMBINED_PROGRAM_PARAM in items_list
            and model.job_type != "multi_manual"
        ):
            return BadRequestResponse(
                f"Unsupported item: {JOB_INFO_COMBINED_PROGRAM_PARAM} for job type: {model.job_type}"
            )

        if JOB_INFO_SSE_LOG_PARAM in items_list and model.job_type != "sse":
            return BadRequestResponse(
                f"Unsupported item: {JOB_INFO_SSE_LOG_PARAM} for job type: {model.job_type}"
            )

        return [
            JobInfoUploadPresignedURL(
                **storage.get_upload_presigned_url_data(key=f"{model.id}/{item}.zip")
            )
            for item in items_list
        ]

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


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
    storage: AbstractStorage = Depends(get_storage),
) -> JobStatusUpdateResponse | ErrorResponse:
    logger.info("invoked get_job")
    try:
        stmt = select(JobModel).where(JobModel.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")

        model_status = parse_job_status(model.status)
        if request.status == JobStatus.running:
            if model_status != JobStatus.ready:
                return ConflictErrorResponse(
                    f"The specified job is not a status that allows transition to the status: {request.status}"
                )
        elif request.status in [
            JobStatus.succeeded,
            JobStatus.failed,
            JobStatus.cancelled,
        ]:
            if model_status != JobStatus.running:
                return ConflictErrorResponse(
                    f"The specified job is not a status that allows transition to the status: {request.status}"
                )
        else:
            return BadRequestResponse(f"Invalid status: {request.status}")

        set_job_status(model, request.status)

        if request.output_files:
            output_files = []
            for s3_key in request.output_files:
                match = re.match(s3_key_pattern, s3_key)
                if match:
                    if match.group("id") == job_id:
                        if storage.does_exist(key=s3_key):
                            output_files.append(match.group("name"))
                        else:
                            return BadRequestResponse(f"{s3_key} not found")
                    else:
                        return ConflictErrorResponse(
                            f"Invalid output file key: {s3_key} for job_id: {job_id}"
                        )
                else:
                    return BadRequestResponse(f"Invalid output file key: {s3_key}")
            model.output_files = json.dumps(output_files)

        if request.message:
            model.message = request.message

        if request.execution_time:
            if request.execution_time < 0:
                return BadRequestResponse("Execution time should not be negative.")
            model.execution_time = request.execution_time

        db.commit()
        return JobStatusUpdateResponse(message="Job status updated")

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.put(
    "/jobs/{job_id}/transpiler_info",
    response_model=UpdateJobTranspilerInfoResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_job_transpiler_info(
    job_id: JobId,
    request: UpdateJobTranspilerInfoRequest,
    db: Session = Depends(get_db),
) -> UpdateJobTranspilerInfoResponse | ErrorResponse:
    logger.info("invoked: update_job_transpiler_info")
    logger.info(
        f"with parameters: job_id={job_id}, request={request.model_dump_json()}"
    )

    try:
        stmt = select(JobModel).where(JobModel.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")

        model.transpiler_info = request.model_dump_json()
        db.commit()
        return UpdateJobTranspilerInfoResponse(
            message="The job's transpiler_info has been updated."
        )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


# TODO: match parameter names of model and schema
MAP_MODEL_TO_SCHEMA = {
    "id": "job_id",
    "owner": "owner",
    "status": "status",
    "name": "name",
    "description": "description",
    "device_id": "device_id",
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


MAP_SCHEMA_TO_MODEL = {v: k for k, v in MAP_MODEL_TO_SCHEMA.items()}


def parse_job_status(s: str) -> JobStatus | ValueError:
    try:
        return JobStatus(s)
    except Exception:
        return ValueError(f"{s} is not a valid JobStatus")


def parse_job_type(jt: str) -> JobType | ValueError:
    try:
        return JobType(jt)
    except Exception:
        return ValueError(f"{jt} is not a valid JobType")


def is_object_field(fld: str) -> bool:
    if fld == "transpiler_info":
        return True
    elif fld == "mitigation_info":
        return True
    elif fld == "simulator_info":
        return True

    return False


def set_job_status(model: JobModel, status: str | JobStatus) -> None:
    if isinstance(status, str):
        status = JobStatus(status)

    model.status = status
    if status == JobStatus.ready:
        if model.ready_at is None:
            model.ready_at = datetime.now(utc)
    elif status == JobStatus.running:
        if model.running_at is None:
            model.running_at = datetime.now(utc)
    elif (
        status == JobStatus.succeeded
        or status == JobStatus.failed
        or status == JobStatus.cancelled
    ):
        if model.ended_at is None:
            model.ended_at = datetime.now(utc)
    return


def model_to_schema(model: JobModel, storage: AbstractStorage) -> JobDef | ValueError:
    status = parse_job_status(model.status)
    if isinstance(status, ValueError):
        return status
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
        input=storage.get_download_presigned_url(
            key=f"{model.id}/{JOB_INFO_INPUT_PARAM}.zip"
        ),
        status=status,
        transpiler_info=json.loads(model.transpiler_info),
        mitigation_info=json.loads(model.mitigation_info),
        simulator_info=json.loads(model.simulator_info),
        execution_time=model.execution_time,
        submitted_at=model.submitted_at,
        ready_at=model.ready_at,
        running_at=model.running_at,
        ended_at=model.ended_at,
    )


def model_to_filtered_schema(
    model: JobModel, storage: AbstractStorage, fields: Optional[list[str]] = None
) -> Job | ValueError:
    if fields is None:
        return model_to_schema(model, storage)
    else:
        dict_schema: dict[str, Any] = {}
        for k in fields:
            if k == "job_id":
                dict_schema["job_id"] = model.id
            elif k == "job_type":
                job_type = parse_job_type(str(model.job_type))
                if isinstance(job_type, ValueError):
                    return job_type
                else:
                    dict_schema[k] = job_type
            elif k == "input":
                dict_schema[k] = storage.get_download_presigned_url(
                    key=f"{model.id}/{JOB_INFO_INPUT_PARAM}.zip"
                )
            elif k == "status":
                status = parse_job_status(model.status)
                if isinstance(status, ValueError):
                    return status
                else:
                    dict_schema[k] = status
            elif is_object_field(k):
                dict_schema[k] = json.loads(getattr(model, k))
            else:
                dict_schema[k] = getattr(model, k)
        return Job(**dict_schema)
