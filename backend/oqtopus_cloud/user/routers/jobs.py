import base64
import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any, Optional, cast

import boto3
import botocore
import pytz
from fastapi import (
    APIRouter,
    Depends,
)
from fastapi import Request as Event
from fastapi_pagination import Page, Params, set_page, set_params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import asc, desc, or_, select
from sqlalchemy.orm import Session, load_only
from uuid_extensions import uuid7
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.jobs import (
    JobBase,
    GetJobStatusResponse,
    GetSselogResponse,
    SubmittedJob,
    RegisteredJob,
    JobStatus,
    JobType,
    RegisterJobResponse,
    SubmitJobRequest,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse

from . import LoggerRouteHandler

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

DEFAULT_PAGE_INDEX = 1
DEFAULT_ITEMS_PER_PAGE = 100

S3_JOB_INFO_INPUT_FILE = "input.zip"
S3_JOB_INFO_OUTPUT_FILE = "output.zip"

DEFAULT_MAX_JOB_INFO_CONTENT_LENGTH_B = 50 * 1024 * 1024  # 50Mb
DEFAULT_PRESIGNED_ULR_EXP_S = 60 * 60  # 1h


class BadRequest(Exception):
    def __init__(self, message: str):
        self.message = message


@router.post(
    "/jobs",
    response_model=RegisterJobResponse,
    responses={
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def register_job(
    event: Event,
    db: Session = Depends(get_db),
) -> RegisterJobResponse | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        job_id = cast(str, uuid7(as_type="str"))  # cast to avoid mypy error
        presigned_data = boto3.client("s3").generate_presigned_post(
            Bucket=os.environ["OQTOPUS_BUCKET"],
            Key=f"{job_id}/{S3_JOB_INFO_INPUT_FILE}",
            Conditions=[
                [
                    "content-length-range",
                    0,
                    int(
                        os.environ.get(
                            "MAX_JOB_INFO_CONTENT_LENGTH",
                            DEFAULT_MAX_JOB_INFO_CONTENT_LENGTH_B,
                        )
                    ),
                ]
            ],
            ExpiresIn=int(
                os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
            ),
        )

        job = Job(
            id=job_id,
            owner=owner,
            status="registered",
            created_at=datetime.now(),
            # dummy data to comply with the NOT NULL DB constraint
            name="",
            device_id="null",
            transpiler_info="null",
            simulator_info="null",
            mitigation_info="null",
            job_type="none",
            shots=0,
        )
        db.add(job)
        db.commit()

        return RegisterJobResponse(job_id=job.id, presigned_url=presigned_data)

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.patch(
    "/jobs/{job_id}",
    response_model=SuccessResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def submit_job(
    event: Event,
    job_id: str,
    request: SubmitJobRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        job = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.status != "registered":
            return BadRequestResponse(
                message=f"{job_id} job is not in valid status for submission (valid status for submission: 'registered')"
            )

        # name is optional
        job.name = validate_name(request)
        # description is optional
        job.description = validate_description(request)

        device = db.get(Device, request.device_id)  # type: ignore
        if device is None:
            return BadRequestResponse(message="device not found")
        if device.status != "available":
            return BadRequestResponse(f"device {device.id} is not available")
        job.device_id = request.device_id

        job.transpiler_info = json.dumps(request.transpiler_info)
        job.simulator_info = json.dumps(request.simulator_info)
        job.mitigation_info = json.dumps(request.mitigation_info)
        job.job_type = JobType(request.job_type)
        job.shots = request.shots
        job.status = JobStatus.submitted
        job.submitted_at = datetime.now()
        job.updated_at = job.submitted_at

        if not validate_job_info(job_id):
            return BadRequestResponse(f"job information for {job_id} job not found")

        db.commit()
        return SuccessResponse(message="job submitted")

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/jobs",
    response_model=list[JobBase | SubmittedJob | RegisteredJob],
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_jobs(
    event: Event,
    fields: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    q: Optional[str] = None,
    order: Optional[str] = None,
    size: Optional[str] = None,
    page: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[JobBase | SubmittedJob | RegisteredJob] | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        # Order Control
        if order == "ASC" or order is None:
            arg_order = asc(Job.created_at)
        elif order == "DESC":
            arg_order = desc(Job.created_at)
        else:
            arg_order = asc(Job.created_at)

        stmt = select(Job).filter(Job.owner == owner).order_by(arg_order)

        # Fields Control
        fields_list = None
        if fields is not None:
            fields_list = fields.split(",")
            valid_fields_list = [
                field in SubmittedJob.model_fields for field in fields_list
            ]
            if all(valid_fields_list):
                # this removes job_info field which doesn't have a relevant model property
                converted_fields_list = [
                    MAP_SCHEMA_TO_MODEL[field]
                    for field in fields_list
                    if field in MAP_SCHEMA_TO_MODEL
                ]
                arg_select = [getattr(Job, field) for field in converted_fields_list]

                # setting up name and job_info in model_to_schema() requires status
                if "name" in arg_select or "job_info" in arg_select:
                    arg_select.append("status")

                # remove duplicated fields
                arg_select = list(dict.fromkeys(arg_select))

                if arg_select:
                    stmt = stmt.options(load_only(*arg_select))
            else:
                invalid_indices = [
                    i for i, field in enumerate(valid_fields_list) if field is False
                ]
                invalid_fields_list = [fields_list[i] for i in invalid_indices]
                return InternalServerErrorResponse(
                    message=f"fields {invalid_fields_list} is invalid"
                )

        # Filtering Jobs
        if start_time is not None:
            stime = datetime.fromisoformat(start_time).astimezone(jst)
            stmt = stmt.filter(Job.created_at >= stime)
        if end_time is not None:
            etime = datetime.fromisoformat(end_time).astimezone(jst)
            stmt = stmt.filter(Job.created_at <= etime)
        if q is not None:
            stmt = stmt.filter(or_(Job.name.contains(q), Job.description.contains(q)))

        set_params(
            Params(
                size=int(size) if size is not None else DEFAULT_ITEMS_PER_PAGE,
                page=int(page) if page is not None else DEFAULT_PAGE_INDEX,
            )
        )
        set_page(Page[Job])
        models = paginate(db, stmt)

        results = []
        for model, job in [
            (model, model_to_schema(model, fields_list)) for model in models.items
        ]:
            results.append(job)
        return results

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


def validate_name(request: SubmitJobRequest) -> str:
    return request.name if request.name is not None else ""


def validate_description(request: SubmitJobRequest) -> str:
    return request.description if (request.description is not None) else ""


def validate_job_info(job_id: str) -> bool:
    try:
        boto3.client("s3").head_object(
            Bucket=os.environ["OQTOPUS_BUCKET"],
            Key=f"{job_id}/{S3_JOB_INFO_INPUT_FILE}",
        )
        return True

    except botocore.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            logger.info(
                f"job information file: {job_id}/{S3_JOB_INFO_INPUT_FILE} not found"
            )
            return False
        else:
            logger.error(
                f"job information file: {job_id}/{S3_JOB_INFO_INPUT_FILE} not accessible"
            )
            raise exc


@router.get(
    "/jobs/{job_id}",
    response_model=SubmittedJob | RegisteredJob,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_job(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> SubmittedJob | RegisteredJob | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner, "job_id": job_id})
        job_model = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job_model is None:
            return NotFoundErrorResponse(message="job not found with the given id")
        job = model_to_schema(job_model)
        if not (isinstance(job, (SubmittedJob, RegisteredJob))):
            raise TypeError("invalid job schema type")
        return job
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.delete(
    "/jobs/{job_id}",
    response_model=SuccessResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
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

        job = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.status not in ["succeeded", "failed", "cancelled"]:
            return BadRequestResponse(
                message=f"{job_id} job is not in valid status for deletion (valid statuses for deletion: 'succeeded', 'failed' and 'cancelled')"
            )

        db.delete(job)
        db.commit()

        # delete the user program and logs from S3 when SSE
        is_success_delete_s3 = delete_s3_folder(job)
        if not is_success_delete_s3:
            return InternalServerErrorResponse(
                message="job deleted successfully, but failed to delete SSE related resources."
            )

        return SuccessResponse(message="job deleted")

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/jobs/{job_id}/status",
    response_model=GetJobStatusResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
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
        return NotFoundErrorResponse(message="job not found with the given id")
    return GetJobStatusResponse(job_id=job_id, status=job.status)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=SuccessResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
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

        job = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.status not in ["ready", "submitted", "running", "cancelled"]:
            return BadRequestResponse(
                message=f"{job_id} job is not in valid status for cancellation (valid statuses for cancellation: 'ready', 'submitted' and 'running')"
            )

        if job.status in ["submitted", "ready", "running"]:
            logger.info(
                "job is in submitted or ready or running state, so it will be marked as cancelled"
            )
            job.status = JobStatus.cancelled
            db.commit()

        return SuccessResponse(message="cancel request accepted")

    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/jobs/{job_id}/sselog",
    response_model=GetSselogResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_sselog(
    event: Event,
    job_id: str,
    db: Session = Depends(get_db),
) -> GetSselogResponse | ErrorResponse:
    owner = event.state.owner
    logger.info("invoked!", extra={"owner": owner, "job_id": job_id})
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    log_name = os.environ["SSE_CONTAINER_LOG_NAME"]
    zip_name = os.environ["SSE_ZIP_FILE_NAME"]

    try:
        # Check the job type, status and the owner
        job_model = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
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
        if job.status != JobStatus.succeeded and job.status != JobStatus.failed:
            logger.info("job has not finished yet")
            return BadRequestResponse(message="job has not finished yet")

        # get the logs from the AWS S3 bucket
        log_object = None
        try:
            log_object = boto3.client("s3").get_object(
                Bucket=bucket_name,
                Key=f"{job_id}/{log_name}",
            )
        except Exception as e:
            logger.exception(f"Failed to get the log file: {str(e)}")

        if log_object is None:
            return NotFoundErrorResponse(message="log file not found")

        log_str = log_object["Body"].read().decode()
        file_name = zip_name.replace("{job_id}", job_id)

        # make a zip stream and encode it to base64
        zip_stream = io.BytesIO()
        with zipfile.ZipFile(
            zip_stream, "w", compression=zipfile.ZIP_DEFLATED
        ) as zip_data:
            zip_data.writestr(log_name, log_str)
        zip_stream.seek(0)
        zip_bin = zip_stream.read()
        zip_base64 = base64.b64encode(zip_bin).decode("utf-8")

        return GetSselogResponse(file=zip_base64, file_name=file_name)

    except Exception as e:
        logger.exception(f"Failed to get the log file: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


def delete_s3_folder(job: Job) -> bool:
    bucket_name = os.environ["OQTOPUS_BUCKET"]
    try:
        s3 = boto3.resource("s3")
        bucket = s3.Bucket(bucket_name)
        deleted_list = bucket.objects.filter(Prefix=f"{job.id}/").delete()
        for deleted in deleted_list:
            if deleted.get("Errors") and len(deleted.get("Errors")) > 0:
                for error in deleted.get("Errors"):
                    logger.error(
                        f"Failed to delete the file from S3: {error.get("Message")}"
                    )
                return False
        return True
    except Exception as e:
        logger.exception(f"Failed to delete the folder from S3: {str(e)}")
        return False


def set_job_failure(job: Job) -> None:
    job.status = JobStatus.failed
    job.ended_at = datetime.now()


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


def model_to_schema(
    model: Job, fields: Optional[list[str]] = None
) -> JobBase | RegisteredJob | SubmittedJob:
    def get_presigned_url(job_id: str, status: str) -> str:
        bucket_name = os.environ["OQTOPUS_BUCKET"]
        filename = (
            S3_JOB_INFO_OUTPUT_FILE
            if status in ["succeeded", "failed", "cancelled"]
            else S3_JOB_INFO_INPUT_FILE
        )
        exp_time = int(
            os.environ.get("PRESIGNED_ULR_EXP_S", DEFAULT_PRESIGNED_ULR_EXP_S)
        )
        return boto3.client("s3").generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": f"{job_id}/{filename}"},
            ExpiresIn=exp_time,
        )

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

    def is_object_field(fld: str) -> bool:
        if fld == "transpiler_info":
            return True
        elif fld == "mitigation_info":
            return True
        elif fld == "simulator_info":
            return True

        return False

    def localize(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return pytz.utc.localize(dt)

    if fields is None:
        if model.status != "registered":
            return SubmittedJob(
                job_id=model.id,
                name=model.name,
                description=model.description,
                device_id=model.device_id,
                shots=model.shots,
                job_type=JobType(model.job_type),
                job_info=get_presigned_url(model.id, model.status),
                status=JobStatus(model.status),
                transpiler_info=json.loads(model.transpiler_info),
                mitigation_info=json.loads(model.mitigation_info),
                simulator_info=json.loads(model.simulator_info),
                execution_time=model.execution_time,
                submitted_at=localize(model.submitted_at),
                ready_at=localize(model.ready_at),
                running_at=localize(model.running_at),
                ended_at=localize(model.ended_at),
            )
        else:
            return RegisteredJob(
                job_id=model.id,
                name=model.name,
                shots=model.shots,
                job_type=JobType(model.job_type),
                status=JobStatus(model.status),
            )
    elif fields is not None:
        dict_schema: dict[str, Any] = {}
        for k in fields:
            if k == "job_id":
                dict_schema[k] = model.id
            elif k == "device_id":
                dict_schema[k] = (
                    model.device_id if model.status != "registered" else None
                )
            elif k == "job_type":
                dict_schema[k] = JobType(model.job_type)
            elif k == "job_info":
                dict_schema[k] = (
                    get_presigned_url(model.id, model.status)
                    if model.status != "registered"
                    else None
                )
            elif k == "status":
                dict_schema[k] = JobStatus(model.status)
            elif is_object_field(k):
                dict_schema[k] = json.loads(getattr(model, k))
            elif is_datetime_field(k):
                dict_schema[k] = localize(getattr(model, k))
            else:
                dict_schema[k] = getattr(model, k)
        return JobBase(**dict_schema)
    else:
        return None
