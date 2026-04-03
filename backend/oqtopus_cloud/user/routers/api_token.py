from argon2 import PasswordHasher
from datetime import datetime, timedelta
from secrets import token_urlsafe

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.api_token import ApiToken, ApiTokenStatus
from oqtopus_cloud.user.schemas.errors import (
    ForbiddenErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

ph = PasswordHasher()


@router.post(
    "/api-token",
    response_model=ApiToken,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def create_api_token(
    event: Event,
    db: Session = Depends(get_db),
) -> (
    ApiToken
    | ForbiddenErrorResponse
    | NotFoundErrorResponse
    | InternalServerErrorResponse
):
    user_id = event.state.user_id
    logger.info(f"Get api token for {user_id}")

    try:
        # generate api token
        api_token_id = token_urlsafe(16)
        api_token_secret = token_urlsafe(16)
        api_token_secret_hash = ph.hash(api_token_secret)
        api_token_expiration = datetime.now(utc).replace(
            second=0, microsecond=0
        ) + timedelta(days=90)

        # save api token to users table (user_id = Cognito username = email)
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalars().first()
        if not user:
            logger.info("User not found")
            return NotFoundErrorResponse(message="User not found")
        if user.userstatus == UserStatus.suspended:  # suspended status
            logger.info("Forbidden")
            return ForbiddenErrorResponse(
                message="this operation is currently unavailable because the status of user is [suspended]"
            )
        else:
            user.api_token_id = api_token_id
            user.api_token_hash = api_token_secret_hash
            user.api_token_expiration = api_token_expiration
            db.commit()
            logger.info("API token created")
            return ApiToken(
                api_token_id=api_token_id,
                api_token_secret=api_token_secret,
                api_token_expiration=api_token_expiration,
            )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/api-token",
    response_model=None,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_api_token(
    event: Event,
    db: Session = Depends(get_db),
) -> (
    Response
    | ForbiddenErrorResponse
    | NotFoundErrorResponse
    | InternalServerErrorResponse
):
    user_id = event.state.user_id
    logger.info(f"Delete api token: {user_id}")
    try:
        # save user table (user_id = Cognito username = email)
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalars().first()
        if not user:
            logger.info("User not found")
            return NotFoundErrorResponse(message="User not found")
        if user.userstatus == UserStatus.suspended:  # suspended status
            logger.info("Forbidden")
            return ForbiddenErrorResponse(message="Forbidden")
        else:
            user.api_token_id = None
            user.api_token_hash = None
            user.api_token_expiration = None
            db.commit()
            logger.info("API token deleted")
            return Response(status_code=status.HTTP_200_OK)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/api-token/status",
    response_model=ApiTokenStatus,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_api_token_status(
    event: Event,
    db: Session = Depends(get_db),
) -> (
    ApiTokenStatus
    | ForbiddenErrorResponse
    | NotFoundErrorResponse
    | InternalServerErrorResponse
):
    user_id = event.state.user_id
    logger.info(f"Get api token: {user_id}")
    try:
        # save user table (user_id = Cognito username = email)
        stmt = select(User).where(User.id == user_id)
        user = db.execute(stmt).scalars().first()
        if not user or user.api_token_hash is None:
            logger.info("User not found")
            return NotFoundErrorResponse(message="User not found")
        if user.userstatus == UserStatus.suspended:  # suspended status
            logger.info("Forbidden")
            return ForbiddenErrorResponse(message="Forbidden")
        else:
            logger.info("API token found")
            api_token_expiration = user.api_token_expiration
            if api_token_expiration is not None:
                api_token_expiration = api_token_expiration.replace(tzinfo=utc)
            return ApiTokenStatus(
                api_token_expiration=api_token_expiration,
            )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")
