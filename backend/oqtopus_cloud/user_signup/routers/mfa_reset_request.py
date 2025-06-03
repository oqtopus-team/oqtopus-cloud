import boto3
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session

from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.conf import logger, tracer
from oqtopus_cloud.user_signup.schemas.errors import (
    BadRequestResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user_signup.schemas.mfa_reset_request import MfaResetRequest

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.put(
    "/mfa_reset_request",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def mfa_reset_request(
    event: Event,
    request: MfaResetRequest,
    db: Session = Depends(get_db),
) -> None | BadRequestResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    pool_id = event.state.pool_id
    email = request.email
    password = request.password
    client_id = request.client_id
    try:
        # confirm cognito authentication
        client = boto3.client("cognito-idp")
        client.admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return BadRequestResponse(message="Failed to authenticate user")
    try:
        logger.info("invoked mfa reset request")
        # check if user exists in users table
        stmt = select(User).where(User.email == email)
        user = db.execute(stmt).scalars().first()
        if not user:
            logger.error(f"User not found: {email}")
            return NotFoundErrorResponse(message="User not found")
        # reset MFA setting for cognito user
        response = client.admin_set_user_mfa_preference(
            # TOTP MFA setting disabled
            SoftwareTokenMfaSettings={"Enabled": False, "PreferredMfa": False},
            Username=email,
            UserPoolId=pool_id,
        )
        logger.info(f"mfa reset response: {response}")
        return None
    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))
