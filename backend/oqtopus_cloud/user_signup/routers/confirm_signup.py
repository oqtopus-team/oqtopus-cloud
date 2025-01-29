import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy.orm import Session

from oqtopus_cloud.common.models.user import User
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
        response = cognito_client.confirm_sign_up(
            ClientId=client_id,
            Username=email,
            ConfirmationCode=confirmation_code,
            ForceAliasCreation=False,
        )
        logger.info(f"response from cognito: {response}")
        admin_response = cognito_client.admin_get_user(
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
        # register the user to users table
        new_user = User(
            cognito_id=cognito_id,
            email=email,
            username=email,
            userstatus=1,
            require_mfa_reset=False,
        )
        db.add(new_user)
        db.commit()
        logger.info(f"User {email} has been confirmed")
        return None
    except ClientError as e:
        # catch the cognito error
        return BadRequestResponse(message=str(e))
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))
