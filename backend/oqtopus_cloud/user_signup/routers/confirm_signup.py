from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session

from oqtopus_cloud.common.i18n import Messages
from oqtopus_cloud.common.models.user import MFAStatus, User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.conf import logger, tracer
from oqtopus_cloud.user_signup.schemas.confirm_signup import ConfirmationSignupRequest
from oqtopus_cloud.user_signup.schemas.errors import (
    BadRequestResponse,
    InternalServerErrorResponse,
    Message,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def cleanup_user(
    db: Session, cognito_client: Any, email: str, user_pool_id: str
) -> None:
    try:
        # rollback the registration of Cognito user
        cognito_client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=email,
        )
        # rollback the registration of user
        stmt = select(User).where(User.email == email)
        user = db.execute(stmt).scalars().first()
        db.delete(user)
        # change the is_signup_completed flag to False
        stmt_whitelist = select(WhitelistUser).where(WhitelistUser.email == email)
        query_whitelist = db.execute(stmt_whitelist).scalars().first()
        if query_whitelist:
            query_whitelist.is_signup_completed = False
        db.commit()
    except Exception as delete_error:
        logger.exception(f"Failed to delete Cognito user: {delete_error}")


@router.put(
    "/confirm_signup",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def confirm_signup(
    event: Event,
    request: ConfirmationSignupRequest,
    db: Session = Depends(get_db),
) -> None | BadRequestResponse | InternalServerErrorResponse:
    client_id = event.state.client_id
    user_pool_id = event.state.pool_id
    try:
        logger.info("invoked signup confirmation")
        email = request.email
        confirmation_code = request.confirmation_code
        # check the confirmation code
        cognito_client = boto3.client("cognito-idp")
        cognito_client.confirm_sign_up(
            ClientId=client_id,
            Username=email,
            ConfirmationCode=confirmation_code,
            ForceAliasCreation=False,
        )
        # change db mfa_status to enabled
        stmt = select(User).where(User.email == email)
        user = db.execute(stmt).scalars().first()
        if user:
            user.mfa_status = MFAStatus.enabled
            db.commit()
        logger.info(f"User {email} has been confirmed")
        return None
    except ClientError as e:
        # catch the cognito error
        message = Messages.SIGNUP_CONFIRMATION_FAILED.format(details=str(e))
        logger.exception(message.message)
        cleanup_user(db, cognito_client, email, user_pool_id)
        return BadRequestResponse(**message.to_dict())
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        cleanup_user(db, cognito_client, email, user_pool_id)
        return InternalServerErrorResponse()
