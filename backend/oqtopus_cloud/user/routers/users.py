from datetime import datetime
from fastapi import APIRouter, Depends, Request as Event, Body, status
import boto3
import pytz
from sqlalchemy import select
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
    BadRequestResponse,
    UnauthorizedResponse,
)
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.user.schemas.users import (
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

        return model_to_schema(user)
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

        if update_user_request.name:
            if len(update_user_request.name) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(update_user_request.name, LEN_VARCHAR)
                )
            query.username = update_user_request.name

        if update_user_request.organization:
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
) -> None | UnauthorizedResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    region = event.state.region
    client = boto3.client("cognito-idp", region_name=region)

    try:
        logger.info("invoked delete user")

        auth_header = event.headers.get("Authorization")
        if not auth_header:
            logger.error("authorization header not found")
            return UnauthorizedResponse(message="authorization header not found")

        token_parts = auth_header.split(" ")
        if len(token_parts) != 2:
            logger.error("authorization header provided with invalid format")
            return UnauthorizedResponse(
                message="authorization header provided with invalid format"
            )

        bearer_prefix, user_access_token = token_parts
        if bearer_prefix.lower() != "bearer":
            logger.error("authorization header provided with invalid format")
            return UnauthorizedResponse(
                message="authorization header provided with invalid format"
            )

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
        if query_result_whitelist:
            query_result_whitelist.is_signup_completed = False
        else:
            logger.warning(
                f"User {query_result.email} is not in whitelist_users. Skipping the change of is_signup_completed."
            )

        # delete from RDS
        db.delete(query_result)
        db.commit()

        # delete from cognito
        client.delete_user(AccessToken=user_access_token)

        return None
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def localize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return pytz.utc.localize(dt)


def model_to_schema(model: User) -> GetOneUserResponse:
    dict = {
        "id": model.id,
        "email": getattr(model, "email", None),
        "name": getattr(model, "username", None),
        "organization": getattr(model, "organization", None),
        "created_at": localize(getattr(model, "created_at", None)),
    }

    return GetOneUserResponse.model_validate(dict)
