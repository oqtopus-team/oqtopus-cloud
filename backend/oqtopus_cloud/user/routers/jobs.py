import json
from datetime import datetime
from typing import Any, Optional, cast
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi import Request as Event
from fastapi_pagination import Page, Params, set_page, set_params
from fastapi_pagination.ext.sqlalchemy import paginate
from opentelemetry import trace
from sqlalchemy import asc, desc, or_, select
from sqlalchemy.orm import Session, load_only
from uuid_extensions import uuid7

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job as JobModel
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import (
    JOB_INFO_INPUT_PARAM,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    ErrorResponse,
    ForbiddenErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.jobs import (
    GetJobStatusResponse,
    Job,
    JobInfo,
    JobInfoUploadPresignedURL,
    JobStatus,
    JobType,
    RegisteredJob,
    RegisterJobResponse,
    SubmitJobRequest,
    SubmittedJob,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

DEFAULT_PAGE_INDEX = 1
DEFAULT_ITEMS_PER_PAGE = 100

S3_JOB_INFO_INPUT_FILE = "input.zip"

DEFAULT_MAX_JOB_INFO_CONTENT_LENGTH_B = 50 * 1024 * 1024  # 50Mb
DEFAULT_PRESIGNED_ULR_EXP_S = 60 * 60  # 1h


class BadRequest(Exception):
    def __init__(self, message: str):
        self.message = message


def annotate_current_span(**attributes: str) -> None:
    current_span = trace.get_current_span()
    if not current_span.is_recording():
        return

    for key, value in attributes.items():
        current_span.set_attribute(key, value)


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
    storage: AbstractStorage = Depends(get_storage),
) -> RegisterJobResponse | ErrorResponse:
    try:
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner})

        job_id = cast(str, uuid7(as_type="str"))  # cast to avoid mypy error
        annotate_current_span(**{"oqtopus.job_id": job_id})

        job = JobModel(
            id=job_id,
            owner=owner,
            status="registered",
            created_at=datetime.now(utc),
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

        return RegisterJobResponse(
            job_id=job.id,
            presigned_url=JobInfoUploadPresignedURL(
                **storage.get_upload_presigned_url_data(
                    key=f"{job_id}/{JOB_INFO_INPUT_PARAM}.zip"
                )
            ),
        )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.post(
    "/jobs/{job_id}/submit",
    response_model=SuccessResponse,
    responses={
        400: {"model": Message},
        403: {"model": Message},
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
    storage: AbstractStorage = Depends(get_storage),
) -> SuccessResponse | ErrorResponse:
    try:
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner})
        annotate_current_span(
            **{
                "oqtopus.job_id": job_id,
                "oqtopus.device_id": request.device_id,
            }
        )

        job = (
            db.query(JobModel)
            .filter(JobModel.id == job_id, JobModel.owner == owner)
            .first()
        )
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
        if not can_user_access_device(owner, request.device_id, db):
            logger.error(
                f"user={owner} is not allowed to create job for device={request.device_id}"
            )
            return ForbiddenErrorResponse(
                message=f"cannot create job for device={request.device_id}"
            )
        job.device_id = request.device_id

        job.transpiler_info = json.dumps(request.transpiler_info or {})
        job.simulator_info = json.dumps(request.simulator_info or {})
        job.mitigation_info = json.dumps(request.mitigation_info or {})
        job.job_type = JobType(request.job_type)
        job.shots = request.shots
        job.status = JobStatus.submitted
        job.submitted_at = datetime.now(utc)
        job.updated_at = job.submitted_at

        if not storage.does_exist(key=f"{job_id}/{S3_JOB_INFO_INPUT_FILE}"):
            return BadRequestResponse(
                f"job information input for {job_id} job not found"
            )

        db.commit()
        return SuccessResponse(message="job submitted")

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def validate_name(request: SubmitJobRequest) -> str:
    return request.name if request.name is not None else ""


def validate_description(request: SubmitJobRequest) -> str:
    return request.description if (request.description is not None) else ""


def can_user_access_device(username: str, device_id: str, db: Session) -> bool:
    try:
        # username here is the email address registered in Cognito
        user = db.scalars(select(User).where(User.email == username)).first()
        if user is None or user.available_devices is None:
            return False

        if user.available_devices == "*":
            return True

        available_devices = json.loads(user.available_devices)

        return isinstance(available_devices, list) and device_id in available_devices
    except Exception:
        return False


@router.get(
    "/jobs",
    response_model=list[Job],
    response_model_exclude_none=True,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_jobs(
    event: Event,
    fields: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    status: Optional[JobStatus] = None,
    q: Optional[str] = None,
    order: Optional[str] = None,
    size: Optional[str] = None,
    page: Optional[str] = None,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> list[Job] | ErrorResponse:
    try:
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner})

        # Order Control
        if order == "ASC" or order is None:
            arg_order = asc(JobModel.created_at)
        elif order == "DESC":
            arg_order = desc(JobModel.created_at)
        else:
            arg_order = asc(JobModel.created_at)

        stmt = (
            select(JobModel)
            .filter(JobModel.owner == owner)
            .order_by(arg_order, JobModel.id)
        )

        # Fields Control
        fields_list = None
        if fields is not None:
            fields_list = fields.split(",")
            valid_fields_list = [field in Job.model_fields for field in fields_list]
            if all(valid_fields_list):
                # this removes job_info field which doesn't have a relevant model property
                converted_fields_list = [
                    MAP_SCHEMA_TO_MODEL[field]
                    for field in fields_list
                    if field in MAP_SCHEMA_TO_MODEL
                ]
                arg_select = [
                    getattr(JobModel, field) for field in converted_fields_list
                ]

                # setting up name and job_info in model_to_filtered_schema() requires status
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
                return BadRequestResponse(
                    message=f"fields {invalid_fields_list} is invalid"
                )

        # Filtering Jobs
        if start_time is not None:
            stime = datetime.fromisoformat(start_time).astimezone(utc)
            stmt = stmt.filter(JobModel.submitted_at >= stime)
        if end_time is not None:
            etime = datetime.fromisoformat(end_time).astimezone(utc)
            stmt = stmt.filter(JobModel.submitted_at <= etime)
        if status is not None:
            stmt = stmt.filter(JobModel.status == status)
        if q is not None:
            stmt = stmt.filter(
                or_(
                    JobModel.id.contains(q),
                    JobModel.name.contains(q),
                    JobModel.description.contains(q),
                )
            )

        set_params(
            Params(
                size=int(size) if size is not None else DEFAULT_ITEMS_PER_PAGE,
                page=int(page) if page is not None else DEFAULT_PAGE_INDEX,
            )
        )
        set_page(Page[JobModel])
        models = paginate(db, stmt)

        results = []
        for model, job in [
            (model, model_to_filtered_schema(model, storage, fields_list))
            for model in models.items
        ]:
            results.append(job)
        return results
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/jobs/{job_id}",
    response_model=Job,
    response_model_exclude_none=True,
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
    storage: AbstractStorage = Depends(get_storage),
) -> RegisteredJob | SubmittedJob | ErrorResponse:
    try:
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner, "job_id": job_id})
        job_model = (
            db.query(JobModel)
            .filter(JobModel.id == job_id, JobModel.owner == owner)
            .first()
        )
        if job_model is None:
            return NotFoundErrorResponse(message="job not found with the given id")
        job = model_to_schema(job_model, storage)
        return job
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


def get_job_info(model: JobModel, storage: AbstractStorage) -> JobInfo:
    output_dict = {}
    if model.output_files:
        output_files = json.loads(model.output_files)
        output_dict = {
            file: storage.get_download_presigned_url(key=f"{model.id}/{file}.zip")
            for file in output_files
        }

    return JobInfo(
        input=storage.get_download_presigned_url(
            key=f"{model.id}/{JOB_INFO_INPUT_PARAM}.zip"
        ),
        message=model.message,
        **output_dict,
    )


def model_to_schema(
    model: JobModel,
    storage: AbstractStorage,
) -> RegisteredJob | SubmittedJob:
    if model.status == "registered":
        return RegisteredJob(
            job_id=model.id,
            status=JobStatus(model.status),
        )
    else:
        return SubmittedJob(
            job_id=model.id,
            name=model.name,
            description=model.description,
            device_id=model.device_id,
            shots=model.shots,
            job_type=JobType(model.job_type),
            job_info=get_job_info(model, storage),
            status=JobStatus(model.status),
            transpiler_info=json.loads(model.transpiler_info),
            mitigation_info=json.loads(model.mitigation_info),
            simulator_info=json.loads(model.simulator_info),
            execution_time=(
                float(model.execution_time)
                if model.execution_time is not None
                else None
            ),
            submitted_at=model.submitted_at,
            ready_at=model.ready_at,
            running_at=model.running_at,
            ended_at=model.ended_at,
        )


def model_to_filtered_schema(
    model: JobModel,
    storage: AbstractStorage,
    fields: list[str] | None = None,
) -> Job:
    def is_object_field(fld: str) -> bool:
        if fld == "transpiler_info":
            return True
        elif fld == "mitigation_info":
            return True
        elif fld == "simulator_info":
            return True

        return False

    if fields is None:
        return model_to_schema(model, storage)
    else:
        dict_schema: dict[str, Any] = {}
        for k in fields:
            if model.status == "registered" and k in [
                "name",
                "device_id",
                "transpiler_info",
                "simulator_info",
                "mitigation_info",
                "job_type",
                "shots",
                "job_info",
            ]:
                # ignore registered job dummy values from DB
                dict_schema[k] = None
            else:
                if k == "job_id":
                    dict_schema[k] = model.id
                elif k == "job_type":
                    dict_schema[k] = JobType(model.job_type)
                elif k == "job_info":
                    dict_schema[k] = get_job_info(model, storage)
                elif k == "status":
                    dict_schema[k] = JobStatus(model.status)
                elif is_object_field(k):
                    dict_schema[k] = json.loads(getattr(model, k))
                else:
                    dict_schema[k] = getattr(model, k)

        return Job(**dict_schema)


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
    storage: AbstractStorage = Depends(get_storage),
) -> SuccessResponse | ErrorResponse:
    try:
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner})

        job = (
            db.query(JobModel)
            .filter(JobModel.id == job_id, JobModel.owner == owner)
            .first()
        )
        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.status not in ["succeeded", "failed", "cancelled"]:
            return BadRequestResponse(
                message=f"{job_id} job is not in valid status for deletion (valid statuses for deletion: 'succeeded', 'failed' and 'cancelled')"
            )

        db.delete(job)
        db.commit()

        is_success_delete_s3 = delete_storage_folder(job, storage)
        if not is_success_delete_s3:
            # error already logged in delete_storage_folder
            return InternalServerErrorResponse(message="Internal Server Error")
        return SuccessResponse(message="job deleted")

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def delete_storage_folder(job: JobModel, storage: AbstractStorage) -> bool:
    def delete_by_key(key: str) -> bool:
        try:
            storage.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete {key}: {str(e)}")
            return False

    try:
        prefix = f"{job.id}/"
        results = storage.traverse_prefix(prefix, delete_by_key)
        return all(results)

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Failed to delete folder for job {job.id}: {str(e)}")
        return False


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
    owner = event.state.user_id
    logger.info("invoked!", extra={"owner": owner})
    job = (
        db.query(JobModel.id, JobModel.status)
        .filter(
            JobModel.id == job_id,
            JobModel.owner == owner,
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
        owner = event.state.user_id
        logger.info("invoked!", extra={"owner": owner})

        job = (
            db.query(JobModel)
            .filter(JobModel.id == job_id, JobModel.owner == owner)
            .first()
        )
        if job is None:
            return NotFoundErrorResponse(message="job not found with the given id")

        if job.status not in [
            "registered",
            "ready",
            "submitted",
            "running",
            "cancelled",
        ]:
            return BadRequestResponse(
                message=f"{job_id} job is not in valid status for cancellation (valid statuses for cancellation: 'registered', 'ready', 'submitted' and 'running')"
            )

        if job.status in ["registered", "submitted", "ready", "running"]:
            logger.info(
                "job is in registered, submitted or ready or running state, so it will be marked as cancelled"
            )
            job.status = JobStatus.cancelled
            db.commit()

        return SuccessResponse(message="cancel request accepted")

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")
