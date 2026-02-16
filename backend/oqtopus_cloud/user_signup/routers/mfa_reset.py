import boto3
from fastapi import APIRouter, Depends, status
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session

from oqtopus_cloud.common.i18n import Messages
from oqtopus_cloud.common.models.user import MFAStatus, User
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user_signup.conf import logger, tracer
from oqtopus_cloud.user_signup.schemas.errors import (
    BadRequestResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
)
from oqtopus_cloud.user_signup.schemas.mfa_reset import (
    MfaResetConfirmTotpRequest,
    MfaResetStartRequest,
    MfaResetStartResponse,
    MfaResetVerifyCodeRequest,
    MfaResetVerifyCodeResponse,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.post(
    "/mfa_reset/start",
    response_model=MfaResetStartResponse,
    responses={
        400: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def mfa_reset_start(
    event: Event,
    request: MfaResetStartRequest,
    db: Session = Depends(get_db),
) -> MfaResetStartResponse | ErrorResponse:
    pool_id = event.state.pool_id
    client_id = event.state.client_id
    email = request.email
    password = request.password
    cognito_client = boto3.client("cognito-idp")

    try:
        # confirm if mfa_status is enabled
        stmt = select(User).where(
            User.email == email, User.mfa_status == MFAStatus.enabled
        )
        user = db.execute(stmt).scalars().first()
        if user:
            message = Messages.MFA_ALREADY_ENABLED.format(id=email)
            logger.info(message.message)
            return BadRequestResponse(**message.to_dict())
        # verify password
        resp = cognito_client.admin_initiate_auth(
            UserPoolId=pool_id,
            ClientId=client_id,
            AuthFlow="ADMIN_NO_SRP_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )
        access_token = resp["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        logger.exception(f"Failed to authenticate user: {str(e)}")
        return BadRequestResponse(**Messages.AUTHENTICATION_FAILED.format().to_dict())
    try:
        # send verification code to user's email
        cognito_client.get_user_attribute_verification_code(
            AccessToken=access_token,
            AttributeName="email",
        )
    except Exception as e:
        logger.exception(f"Failed to send verification code: {str(e)}")
        return InternalServerErrorResponse()
    logger.info("Verification code sent successfully")
    return MfaResetStartResponse(access_token=access_token)


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
    db: Session = Depends(get_db),
) -> MfaResetVerifyCodeResponse | ErrorResponse:
    access_token = request.access_token
    code = request.code
    cognito_client = boto3.client("cognito-idp")
    # verify the confirmation code
    try:
        cognito_client.verify_user_attribute(
            AccessToken=access_token,
            AttributeName="email",
            Code=code,
        )
    except Exception as e:
        logger.exception(f"Failed to verify code: {str(e)}")
        return BadRequestResponse(
            **Messages.CODE_VERIFICATION_FAILED.format().to_dict()
        )
    try:
        resp = cognito_client.associate_software_token(AccessToken=access_token)
    except Exception as e:
        logger.exception(f"Failed to associate software token: {str(e)}")
        return InternalServerErrorResponse()
    logger.info("Software token associated successfully")
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
    access_token = request.access_token
    totp_code = request.totp_code
    cognito_client = boto3.client("cognito-idp")
    # verify the TOTP code
    try:
        cognito_client.verify_software_token(
            AccessToken=access_token,
            UserCode=totp_code,
        )
        response = cognito_client.get_user(AccessToken=access_token)
        cognito_id = None
        for attr in response["UserAttributes"]:
            if attr["Name"] == "sub":
                cognito_id = attr["Value"]
                break
        logger.info(cognito_id)
    except Exception as e:
        logger.exception(f"Invalid TOTP code: {str(e)}")
        return BadRequestResponse(**Messages.INVALID_TOTP_CODE.format().to_dict())

    try:
        # update user's MFA preference to enable TOTP
        cognito_client.set_user_mfa_preference(
            AccessToken=access_token,
            SoftwareTokenMfaSettings={"Enabled": True, "PreferredMfa": True},
        )
        # update user's MFA status to enabled in the database
        stmt = select(User).where(User.cognito_id == cognito_id)
        user = db.execute(stmt).scalar()
        if user:
            user.mfa_status = MFAStatus.enabled
            db.commit()
    except Exception as e:
        logger.exception(f"Failed to set user MFA preference: {str(e)}")
        return InternalServerErrorResponse()
    logger.info("MFA reset confirmed successfully")
    return None
