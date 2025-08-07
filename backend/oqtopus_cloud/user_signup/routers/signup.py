import boto3
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session

from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.conf import logger, tracer
from oqtopus_cloud.user_signup.schemas.errors import (
    BadRequestResponse,
    InternalServerErrorResponse,
    Message,
)
from oqtopus_cloud.user_signup.schemas.signup import SignupRequest

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.post(
    "/signup",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def signup(
    event: Event,
    request: SignupRequest,
    db: Session = Depends(get_db),
) -> None | BadRequestResponse | InternalServerErrorResponse:
    client_id = event.state.client_id
    user_pool_id = event.state.pool_id
    try:
        logger.info("invoked pre signup confirmation")
        # check if user exists in whitelist_users table
        email = request.email
        password = request.password
        stmt_whitelist = select(WhitelistUser).where(WhitelistUser.email == email)
        whitelist_user = db.execute(stmt_whitelist).scalars().first()
        if not whitelist_user:
            logger.error(f"Not in whitelist_users: {email}")
            return BadRequestResponse(message="Not in whitelist_users")
        # cognito sign up
        client = boto3.client("cognito-idp")
        response = client.sign_up(
            ClientId=client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
            ],
            ValidationData=[],
        )
        logger.info(f"response: {response}")
        # register the user to users table
        admin_response = client.admin_get_user(
            UserPoolId=user_pool_id,
            Username=email,
        )
        cognito_id = next(
            (
                attr["Value"]
                for attr in admin_response["UserAttributes"]
                if attr["Name"] == "sub"
            ),
            None,
        )
        new_user = User(
            cognito_id=cognito_id,
            email=email,
            username=whitelist_user.username,
            userstatus=UserStatus.approved,
            organization=whitelist_user.organization,
            group_id=whitelist_user.group_id,
            available_devices=whitelist_user.available_devices,
        )
        db.add(new_user)
        # update whitelist_user status to completed
        whitelist_user.is_signup_completed = True
        db.commit()
        return None
    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))
