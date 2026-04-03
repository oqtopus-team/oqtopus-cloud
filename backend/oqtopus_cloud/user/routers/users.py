import json
from os import environ
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request as Event, Body, status
import boto3
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.user.common.settings import get_editable_fields, get_visible_fields
from oqtopus_cloud.user.schemas.jobs import JobType
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from oqtopus_cloud.user.common.validation_utils import (
    FIELD_TOO_LONG_MESSAGE,
    LEN_VARCHAR,
    FormatError,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
    ForbiddenErrorResponse,
    BadRequestResponse,
    UnauthorizedResponse,
)
from oqtopus_cloud.common.session import (
    get_db,
    get_cognito_client,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.user.schemas.users import (
    LoginEvent,
    GetOneUserResponse,
    UpdateUserRequest,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/users/me", response_model=GetOneUserResponse, responses={500: {"model": Message}}
)
@tracer.capture_method
def get_user(
    event: Event,
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    logger.info("invoked get user")
    try:
        user = db.scalars(select(User).where(User.email == event.state.owner)).first()

        if user is None:
            message = "user is not found"
            logger.info(message)
            return NotFoundErrorResponse(message=message)

        login_events = (
            retrieve_user_login_history(user.cognito_id, event.state.region)
            if environ.get("LOGIN_HISTORY_ENABLED", "false").upper() == "TRUE"
            else None
        )

        return model_to_schema(user, login_events)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.patch(
    "/users/me",
    response_model=GetOneUserResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_user(
    event: Event,
    update_user_request: UpdateUserRequest = Body(..., description="user update"),
    db: Session = Depends(get_db),
) -> (
    GetOneUserResponse
    | NotFoundErrorResponse
    | UnauthorizedResponse
    | BadRequestResponse
    | InternalServerErrorResponse
):
    try:
        logger.info("invoked update user")
        # search the user
        stmt = select(User).where(User.email == event.state.owner)
        query = db.execute(stmt).scalars().first()
        if not query:
            logger.error("user not found")
            return NotFoundErrorResponse(message="user not found")

        editable_fields = get_editable_fields()

        if update_user_request.name:
            if "name" not in editable_fields:
                logger.error("name field is disabled for updates")
                return UnauthorizedResponse(
                    message="name field is disabled for updates"
                )
            if len(update_user_request.name) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(update_user_request.name, LEN_VARCHAR)
                )
            query.username = update_user_request.name

        if update_user_request.organization:
            if "organization" not in editable_fields:
                logger.error("organization field is disabled for updates")
                return UnauthorizedResponse(
                    message="organization field is disabled for updates"
                )
            if len(update_user_request.organization) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(
                        update_user_request.organization, LEN_VARCHAR
                    )
                )
            query.organization = update_user_request.organization

        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except FormatError as e:
        logger.exception(f"error: {str(e)}")
        return BadRequestResponse(message=str(e))
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/users/me",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_user(
    event: Event,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
    client=Depends(get_cognito_client),
) -> (
    None | ForbiddenErrorResponse | NotFoundErrorResponse | InternalServerErrorResponse
):
    user_pool_id = event.state.user_pool_id

    try:
        logger.info("invoked delete user")

        if environ.get("ALLOW_DELETION", "false").upper() != "TRUE":
            logger.error("user deletion is disabled")
            return ForbiddenErrorResponse(message="user deletion is disabled")

        # query
        stmt = select(User).where(User.email == event.state.owner)
        # pagination
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            logger.error("User not found")
            return NotFoundErrorResponse(message="User not found")

        # check if the user is in whitelist_users
        stmt_whitelist = select(WhitelistUser).where(
            WhitelistUser.email == query_result.email
        )
        query_result_whitelist = db.execute(stmt_whitelist).scalars().first()
        stmt_sse_jobs = select(Job).where(
            Job.owner == query_result.email, Job.job_type == JobType.sse
        )
        user_sse_jobs = db.scalars(stmt_sse_jobs).all()
        stmt_delete_user_jobs = delete(Job).where(Job.owner == query_result.email)

        # delete from RDS
        db.execute(stmt_delete_user_jobs)
        db.delete(query_result)

        if query_result_whitelist:
            db.delete(query_result_whitelist)
        else:
            logger.warning(
                f"User {query_result.email} is not in whitelist_users. Skipping whitelist_users deletion."
            )
        db.commit()

        for user_sse_job in user_sse_jobs:
            # delete the user program and logs from S3 when SSE
            is_success_delete_s3 = delete_storage_folder(user_sse_job, storage)
            if not is_success_delete_s3:
                # error already logged in delete_storage_folder
                return InternalServerErrorResponse(message="Internal Server Error")

        # delete from cognito
        client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=query_result.email,
        )

        return None
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def retrieve_user_login_history(cognito_id: str, region: str) -> list[LoginEvent]:
    client = boto3.client("cloudtrail", region_name=region)
    paginator = client.get_paginator("lookup_events")
    filter_attributes = [
        {"AttributeKey": "EventSource", "AttributeValue": "cognito-idp.amazonaws.com"}
    ]
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=3)

    event_list: list[LoginEvent] = []
    for page in paginator.paginate(
        LookupAttributes=filter_attributes, StartTime=start_time, EndTime=end_time
    ):
        for raw_event in page["Events"]:
            event = json.loads(raw_event["CloudTrailEvent"])
            if event["eventName"] != "RespondToAuthChallenge":
                continue

            response_elements = event["responseElements"]
            if (
                response_elements is None
                or response_elements.get("authenticationResult", {}).get("accessToken")
                is None
            ):
                continue

            if (
                "additionalEventData" not in event
                or event["additionalEventData"]["sub"] != cognito_id
            ):
                continue

            event_list.append(
                LoginEvent(
                    # eventTime is in UTC by default, no need to localize it
                    event_date=event["eventTime"],
                    user_agent=event["userAgent"],
                    ip=event["sourceIPAddress"],
                )
            )

    return event_list


def delete_storage_folder(job: Job, storage: AbstractStorage) -> bool:
    if job.job_type != JobType.sse:
        return True

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


def model_to_schema(
    model: User, login_events: list[LoginEvent] | None = None
) -> GetOneUserResponse:
    visible_fields = get_visible_fields()

    dict = {
        "id": model.id if "id" in visible_fields else None,
        "email": getattr(model, "email", None) if "email" in visible_fields else None,
        "name": getattr(model, "username", None) if "name" in visible_fields else None,
        "organization": getattr(model, "organization", None)
        if "organization" in visible_fields
        else None,
        "created_at": getattr(model, "created_at", None)
        if "created_at" in visible_fields
        else None,
        "login_events": login_events,
    }

    return GetOneUserResponse.model_validate(dict)
