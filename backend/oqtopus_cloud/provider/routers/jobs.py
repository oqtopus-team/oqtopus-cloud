import base64
import json
import os
import re
from datetime import datetime
from typing import Optional

import boto3
import pytz
from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import PlainTextResponse
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
    JobInfoUploadPresignedURL,
    JobStatus,
    JobStatusUpdate,
    JobStatusUpdateResponse,
    JobType,
    UpdateJobTranspilerInfoRequest,
    UpdateJobTranspilerInfoResponse,
    UploadSselogResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

JobId = str

JOB_INFO_INPUT_PARAM = "input"
JOB_INFO_COMBINED_PROGRAM_PARAM = "combined_program"
JOB_INFO_RESULT_PARAM = "result"
JOB_INFO_TRANSPILE_RESULT_PARAM = "transpile_result"
JOB_INFO_SSE_LOG_PARAM = "sse_log"

s3_key_pattern = r"^(?P<id>[\w-]+)/(?P<name>input|combined_program|result|transpile_result|sse_log)\.zip$"

DEFAULT_PRESIGNED_ULR_EXP_S = 60 * 60  # 1h
DEFAULT_MAX_UPLOAD_CONTENT_LENGTH_B = 50 * 1024 * 1024  # 50Mb


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
        select_stmt = select(Job).filter(
            Job.device_id == device_id, Job.status != "registered"
        )

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
                select_stmt = select_stmt.options(load_only(*arg_select))
            else:
                invalid_indices = [
                    i for i, field in enumerate(valid_fields_list) if field is False
                ]
                invalid_fields_list = [fields_list[i] for i in invalid_indices]
                return InternalServerErrorResponse(
                    message=f"fields {invalid_fields_list} is invalid"
                )

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
                    if match.group("id") != job_id:
                        return BadRequestResponse(
                            f"Invalid output file key: {s3_key} for job_id: {job_id}"
                        )
                    output_files.append(match.group("name"))
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
        return InternalServerErrorResponse(f"Error: {str(e)}")


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
        stmt = select(Job).where(Job.id == job_id)
        model = db.execute(stmt).scalar_one_or_none()
        if model is None:
            return NotFoundErrorResponse("Job not found")

        model.transpiler_info = request.model_dump_json()
        db.commit()
        return UpdateJobTranspilerInfoResponse(
            message="The job's transpiler_info has been updated."
        )

    except Exception as e:
        logger.error(e)
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.get(
    "/jobs/{job_id}/ssesrc",
    response_model=None,
    response_class=PlainTextResponse,
    responses={
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_ssesrc(
    job_id: str,
) -> PlainTextResponse | ErrorResponse:
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    file_name = os.environ["SSE_USER_PROGRAM_NAME"]
    try:
        # get the program file from the AWS S3 bucket
        s3_client = boto3.client("s3")
        program = s3_client.get_object(
            Bucket=bucket_name,
            Key=f"{job_id}/{file_name}",
        )
        program = program["Body"].read()

        # encode the file to base64
        program_base64 = base64.b64encode(program).decode("utf-8")
        return PlainTextResponse(content=program_base64)

    except Exception as e:
        logger.exception("Failed to get SSE user program file: %s", e)
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/jobs/{job_id}/sselog",
    response_model=UploadSselogResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def upload_sselog(
    job_id: str,
    file: UploadFile = Form(...),
    db: Session = Depends(get_db),
) -> UploadSselogResponse | ErrorResponse:
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    file_name = os.environ["SSE_CONTAINER_LOG_NAME"]

    try:
        # Check that the job exists
        job_model = db.query(Job).filter(Job.id == job_id).first()
        if job_model is None:
            logger.info("job not found with the given id")
            return NotFoundErrorResponse(message="job not found with the given id")
        job = model_to_schema(job_model)
        if isinstance(job, ValueError):
            logger.warning("warn: Failed to encode job model to schema.")
            return NotFoundErrorResponse(message="job not found with the given id")
        if job.job_type != JobType.sse:
            logger.info("job is not an SSE job")
            return BadRequestResponse(message="job is not an SSE job")

        binary = file.file.read()

        s3_client = boto3.client("s3")
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f"{job_id}/{file_name}",
            Body=binary,
        )
        return UploadSselogResponse(message="SSE log uploaded")
    except Exception as e:
        logger.exception("Failed to upload SSE log file: %s", e)
        return InternalServerErrorResponse(f"Error: {str(e)}")


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


def get_download_presigned_url(bucket: str, key: str) -> str:
    return boto3.client("s3").generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
        },
        ExpiresIn=int(
            os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
        ),
    )


def get_upload_presigned_url(bucket: str, key: str) -> JobInfoUploadPresignedURL:
    presigned_data = boto3.client("s3").generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Conditions=[
            [
                "content-length-range",
                0,
                int(
                    os.environ.get(
                        "MAX_UPLOAD_CONTENT_LENGTH",
                        DEFAULT_MAX_UPLOAD_CONTENT_LENGTH_B,
                    )
                ),
            ]
        ],
        ExpiresIn=int(
            os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
        ),
    )
    return JobInfoUploadPresignedURL(**presigned_data)


def model_to_schema(
    model: Job, fields: Optional[list[str]] = None
) -> JobDef | ValueError:
    status = parse_job_status(model.status)
    if isinstance(status, ValueError):
        return status
    job_type = parse_job_type(str(model.job_type))
    if isinstance(job_type, ValueError):
        return job_type

    bucket_name = os.environ["OQTOPUS_BUCKET"]
    job_info = JobInfo(
        input=get_download_presigned_url(
            bucket_name, f"{model.id}/{JOB_INFO_INPUT_PARAM}.zip"
        ),
        combined_program=get_upload_presigned_url(
            bucket_name, f"{model.id}/{JOB_INFO_COMBINED_PROGRAM_PARAM}.zip"
        ),
        result=get_upload_presigned_url(
            bucket_name, f"{model.id}/{JOB_INFO_RESULT_PARAM}.zip"
        ),
        transpile_result=get_upload_presigned_url(
            bucket_name, f"{model.id}/{JOB_INFO_TRANSPILE_RESULT_PARAM}.zip"
        ),
        sse_log=get_upload_presigned_url(
            bucket_name, f"{model.id}/{JOB_INFO_SSE_LOG_PARAM}.zip"
        )
        if model.job_type == "sse"
        else None,
    )

    return JobDef(
        job_id=model.id,
        name=model.name,
        description=model.description,
        device_id=model.device_id,
        shots=model.shots,
        job_type=job_type,
        job_info=job_info,
        status=status,
        transpiler_info=json.loads(model.transpiler_info),
        mitigation_info=json.loads(model.mitigation_info),
        simulator_info=json.loads(model.simulator_info),
        execution_time=model.execution_time,
        submitted_at=localize(model.submitted_at),
        ready_at=localize(model.ready_at),
        running_at=localize(model.running_at),
        ended_at=localize(model.ended_at),
    )
