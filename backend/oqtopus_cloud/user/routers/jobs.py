import base64
import io
import json
import os
import zipfile
from datetime import datetime
from typing import Any, Optional

import boto3
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
    GetJobsResponse,
    GetJobStatusResponse,
    GetSselogResponse,
    JobDef,
    JobInfo,
    JobStatus,
    JobType,
    SubmitJobInfo,
    SubmitJobRequest,
    SubmitJobResponse,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse

from . import LoggerRouteHandler

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

DEFAULT_PAGE_INDEX = 1
DEFAULT_ITEMS_PER_PAGE = 100


class BadRequest(Exception):
    def __init__(self, message: str):
        self.message = message


@router.get(
    "/jobs",
    response_model=list[GetJobsResponse | JobDef],
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
) -> list[GetJobsResponse | JobDef] | ErrorResponse:
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
                stmt = (
                    select(Job)
                    .filter(Job.owner == owner)
                    .order_by(arg_order)
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
            stmt = select(Job).filter(Job.owner == owner).order_by(arg_order)

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
            if isinstance(job, ValueError):
                logger.warning(str(job))
                # ignore illegal jobs
                continue
            else:
                results.append(job)
        return results
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


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
    responses={400: {"model": Message}, 500: {"model": Message}},
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
            return BadRequestResponse(message="device not found")
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        if device.status != "available":
            return BadRequestResponse(f"device {device.id} is not available")
        if request.job_type not in jobtype_of_jobinfo(request.job_info):
            return BadRequestResponse("job_info is not compatible with job_type")

        # NOTE: method and operator is validated by pydantic
        shots = request.shots
        # name is optional
        name = validate_name(request)

        # description is optional
        description = validate_description(request)

        job = Job(
            id=uuid7(as_type="str"),
            owner=owner,
            name=name,
            description=description,
            device_id=request.device_id,
            job_info=json.dumps(request.job_info.model_dump()),
            transpiler_info=json.dumps(request.transpiler_info),
            simulator_info=json.dumps(request.simulator_info),
            mitigation_info=json.dumps(request.mitigation_info),
            job_type=request.job_type,
            shots=shots,
            submitted_at=datetime.now(),
            created_at=datetime.now(),
        )

        # put the user program to S3 when SSE
        is_success_put_s3 = put_user_program_to_s3(job)
        if not is_success_put_s3:
            return InternalServerErrorResponse(
                message="Failed to upload the user program to S3"
            )

        db.add(job)
        db.commit()
        return SubmitJobResponse(job_id=job.id)
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/jobs/{job_id}",
    response_model=JobDef,
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
) -> JobDef | GetJobsResponse | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner, "job_id": job_id})
        job_model = db.query(Job).filter(Job.id == job_id, Job.owner == owner).first()
        if job_model is None:
            return NotFoundErrorResponse(message="job not found with the given id")
        job = model_to_schema(job_model)
        if isinstance(job, ValueError):
            logger.warning("warn: Failed to encode job model to schema.")
            return NotFoundErrorResponse(message="job not found with the given id")
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
        job = db.get(Job, job_id)

        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.owner != owner or job.status not in ["succeeded", "failed", "cancelled"]:
            return NotFoundErrorResponse(
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

        job = db.get(Job, job_id)

        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")
        if job.owner != owner or job.status not in [
            "ready",
            "submitted",
            "running",
            "cancelled",
        ]:
            return NotFoundErrorResponse(
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
    bucket_name = os.environ["SSE_BUCKET"]
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
            s3_client = boto3.client("s3")
            log_object = s3_client.get_object(
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


def put_user_program_to_s3(job: Job) -> bool:
    if job.job_type != JobType.sse:
        return True

    bucket_name = os.environ["SSE_BUCKET"]
    file_name = os.environ["SSE_USER_PROGRAM_NAME"]
    try:
        job_info = decode_job_info(json.loads(job.job_info))
        if isinstance(job_info, ValueError):
            return False
        if (
            job_info.program is None
            or len(job_info.program) == 0
            or job_info.program[0] == ""
        ):
            logger.error("the job has no program")
            return False

        # decode the base64 encoded program
        decoded_program = base64.b64decode(job_info.program[0])
        # upload the program to the AWS S3 bucket
        s3_client = boto3.client("s3")
        s3_client.put_object(
            Bucket=bucket_name,
            Key=f"{job.id}/{file_name}",
            Body=decoded_program,
        )

        return True
    except Exception as e:
        logger.exception(f"Failed to upload the user program to S3: {str(e)}")
        return False


def delete_s3_folder(job: Job) -> bool:
    if job.job_type != JobType.sse:
        return True

    bucket_name = os.environ["SSE_BUCKET"]
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


def decode_job_info(j: Any) -> JobInfo | ValueError:
    try:
        jobinfo = JobInfo.model_validate(j)
        return jobinfo
    except Exception as e:
        return ValueError(f"Failed to decode job_info: {str(e)}")


def model_to_schema(
    model: Job, fields: Optional[list[str]] = None
) -> JobDef | GetJobsResponse | ValueError:
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

    job_info = decode_job_info(json.loads(model.job_info))

    if fields is None:
        job_info = decode_job_info(json.loads(model.job_info))
        if isinstance(job_info, ValueError):
            return job_info
        return JobDef(
            job_id=model.id,
            name=model.name,
            description=model.description,
            device_id=model.device_id,
            shots=model.shots,
            job_type=JobType(model.job_type),
            job_info=job_info,
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
    elif fields is not None:
        dict_schema: dict[str, Any] = {}
        for k in fields:
            if k == "job_id":
                dict_schema["job_id"] = model.id
            elif k == "job_type":
                dict_schema[k] = JobType(model.job_type)
            elif k == "job_info":
                job_info = decode_job_info(json.loads(model.job_info))
                if isinstance(job_info, ValueError):
                    return job_info
                else:
                    dict_schema[k] = job_info
            elif k == "status":
                dict_schema[k] = JobStatus(model.status)
            elif is_object_field(k):
                dict_schema[k] = json.loads(getattr(model, k))
            elif is_datetime_field(k):
                dict_schema[k] = localize(getattr(model, k))
            else:
                dict_schema[k] = getattr(model, k)
        return GetJobsResponse(**dict_schema)
    else:
        return None


def jobtype_of_jobinfo(info: SubmitJobInfo) -> list[JobType]:
    if info.operator is not None:
        return [JobType.estimation]
    else:
        return [JobType.sampling, JobType.multi_manual, JobType.sse]
