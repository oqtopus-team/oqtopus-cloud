import boto3
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy.orm import Session

from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.conf import logger, tracer
from oqtopus_cloud.user_signup.schemas.errors import (
    BadRequestResponse,
    ErrorResponse,
    Message,
)
from oqtopus_cloud.user_signup.schemas.mfa_reset import (
    MfaResetConfirmTotpRequest,
    MfaResetStartRequest,
    MfaResetVerifyCodeRequest,
    MfaResetVerifyCodeResponse,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)
cognito_client = boto3.client("cognito-idp")


@router.post(
    "/mfa_reset/start",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def mfa_reset_start(
    event: Event,
    request: MfaResetStartRequest,
) -> None | ErrorResponse:
    pool_id = event.state.pool_id
    client_id = event.state.client_id
    email = request.email
    password = request.password

    # verify password
    try:
        resp = cognito_client.admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        access_token = resp["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        logger.exception(f"Failed to authenticate user: {str(e)}")
        return BadRequestResponse(message="Failed to authenticate user")

    # send verification code to user's email
    cognito_client.get_user_attribute_verification_code(
        AccessToken=access_token,
        AttributeName="email",
    )
    return None


@router.post(
    "/mfa_reset/verify_code",
    response_model=MfaResetVerifyCodeResponse,
    responses={
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def mfa_reset_verify_code(
    event: Event,
    request: MfaResetVerifyCodeRequest,
) -> MfaResetVerifyCodeResponse | ErrorResponse:
    pool_id = event.state.pool_id
    client_id = event.state.client_id
    email = request.email
    password = request.password
    code = request.code

    # obtain access token to verify the code
    try:
        resp = cognito_client.admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        access_token = resp["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        logger.exception(f"Failed to authenticate user: {str(e)}")
        return BadRequestResponse(message="Failed to authenticate user")

    # verify the confirmation code
    try:
        cognito_client.verify_user_attribute(
            AccessToken=access_token,
            AttributeName="email",
            Code=code,
        )
    except Exception as e:
        logger.exception(f"Failed to verify code: {str(e)}")
        return BadRequestResponse(message="Failed to verify code")

    resp = cognito_client.associate_software_token(AccessToken=access_token)
    return MfaResetVerifyCodeResponse(secret=resp.get("SecretCode"))


@router.post(
    "/mfa_reset/confirm_totp",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def mfa_reset_confirm_totp(
    event: Event,
    request: MfaResetConfirmTotpRequest,
    db: Session = Depends(get_db),
) -> None | ErrorResponse:
    pool_id = event.state.pool_id
    client_id = event.state.client_id
    email = request.email
    password = request.password
    totp_code = request.totp_code
    try:
        # obtain access token to confirm TOTP
        resp = cognito_client.admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        access_token = resp["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        logger.exception(f"Failed to authenticate user: {str(e)}")
        return BadRequestResponse(message="Failed to authenticate user")

    # verify the TOTP code
    try:
        cognito_client.verify_software_token(
            AccessToken=access_token,
            UserCode=totp_code,
        )
    except Exception:
        return BadRequestResponse(message="Invalid TOTP code. Please try again.")

    # update user's MFA preference to enable TOTP
    cognito_client.set_user_mfa_preference(
        AccessToken=access_token,
        SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
    )
    return None
