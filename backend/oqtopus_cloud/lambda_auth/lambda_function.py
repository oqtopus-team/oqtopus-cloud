import os
from datetime import datetime
from typing import Optional

import boto3
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from botocore.config import Config
from sqlalchemy import select, update
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.user import MFAStatus, User, UserStatus
from oqtopus_cloud.common.session import AUTH_DB_READ_TIMEOUT_SECONDS, _create_session
from oqtopus_cloud.lambda_auth.conf import logger, tracer

utc = ZoneInfo("UTC")

ph = PasswordHasher()

# Per-call timeouts so a stalled external dependency raises a Python
# exception (visible in CloudWatch + X-Ray) instead of consuming the
# Lambda timeout budget and being SIGKILL'd. Normal latencies observed:
# Cognito IDP ~120ms, JWKS fetch ~150ms. read_timeout=3s gives ~20x
# headroom over normal while still failing fast on a real stall; with
# total_max_attempts=2 (one initial + one retry) the SDK-level worst case
# is ~7s (3s read + 1s backoff + 3s read), comfortably under the 15s
# Lambda timeout. connect_timeout=2s bounds the TCP+TLS handshake
# (anything beyond is anomalous).
#
# NB: use total_max_attempts, NOT max_attempts. In a botocore retries
# config, max_attempts means *retries excluding the initial call*
# (max_attempts=N -> total_max_attempts=N+1), so max_attempts=2 would be
# 3 calls (~11s) and blow the worst-case budget above.
_BOTO_TIMEOUT_CONFIG = Config(
    connect_timeout=2,
    read_timeout=3,
    retries={"total_max_attempts": 2, "mode": "standard"},
)
_JWKS_HTTP_TIMEOUT_SECONDS = 5


class AuthError(Exception):
    """Custom exception for authentication errors"""

    pass


@tracer.capture_method
def _validate_user_status(
    user_id: str | None = None, cognito_id: str | None = None
) -> bool:
    try:
        # Get a database session
        db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
        try:
            user = None
            # Get the user status from the database
            if user_id:
                stmt = select(User).where(
                    User.id == user_id,
                    User.userstatus == UserStatus.approved,
                )
                user = db.execute(stmt).scalar()
            elif cognito_id:
                stmt = select(User).where(
                    User.cognito_id == cognito_id,
                    User.userstatus == UserStatus.approved,
                )
                user = db.execute(stmt).scalar()
            else:
                raise AuthError("user_id or cognito_id is not given")
        finally:
            db.close()

        if user is None:
            logger.info(f"User {user_id} or {cognito_id} is not approved")
            return False
        # Get the MFA status from the database
        # only for the case from oqtopus-frontend
        if user_id and user.mfa_status != MFAStatus.enabled:
            raise AuthError("MFA is not enabled for this user")
        return True
    except Exception as e:
        logger.error(f"Failed to get user status: {e}")
        raise AuthError("Failed to get user status")


def _validate_headers_for_api_token(headers: dict) -> None:
    api_token = headers.get("q-api-token")
    authorization = headers.get("authorization")

    # validate that both headers are present and match
    if not authorization or not api_token:
        raise AuthError(
            f"Authentication header is missing: authorization={authorization}, q-api-token={api_token}"
        )

    if authorization != api_token:
        raise AuthError(
            f"Authorization and q-api-token do not match: authorization={authorization}, q-api-token={api_token}"
        )


@tracer.capture_method
def _verify_id_token(id_token: Optional[str]) -> str:
    if id_token is None:
        raise AuthError("ID token is not found")

    id_token = id_token.replace("Bearer ", "")

    # Get environment variables
    try:
        REGION = os.environ["REGION"]
        USER_POOL_ID = os.environ["AUTH_USER_POOL_ID"]
        CLIENT_ID = os.environ["USER_POOL_WEB_CLIENT_ID"]
    except Exception as e:
        raise AuthError(f"Environment variable is not set {e}")

    # Construct the issuer and JWKS URL for the Cognito user pool
    issuer = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
    jwks_url = f"{issuer}/.well-known/jwks.json"

    try:
        # Get the signing key from the JWT
        jwks_client = jwt.PyJWKClient(jwks_url, timeout=_JWKS_HTTP_TIMEOUT_SECONDS)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    except Exception as e:
        raise AuthError(f"Failed to get signing key from JWT: {e}")

    try:
        # Decode and verify the ID token
        token = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=issuer,
            options={
                "require": ["exp", "iss", "aud"],
                "verify_iss": True,
                "verify_exp": True,
                "verify_aud": True,
            },
        )

        # verify the token_use claim
        if token["token_use"] != "id":
            raise AuthError("Invalid token_use")

        # verify the user status
        if not _validate_user_status(user_id=token["cognito:username"]):
            raise AuthError("User is not approved")

        return token["cognito:username"]
    except Exception:
        raise AuthError("ID token is invalid")


@tracer.capture_method
def _verify_api_token(api_token: Optional[str]) -> str:
    if api_token is None or api_token == "":
        raise AuthError("API token is None")

    try:
        api_token_id, api_token_secret = api_token.split(".")
    except ValueError:
        raise AuthError("API token is malformed")

    # Get environment variables
    try:
        USER_POOL_ID = os.environ["AUTH_USER_POOL_ID"]
    except Exception as e:
        raise AuthError(f"Environment variable is not set {e}")

    try:
        # Get a database session
        db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
        try:
            select_stmt = select(
                User.mfa_status,
                User.api_token_hash,
                User.api_token_expiration,
                User.cognito_id,
            ).where(User.api_token_id == api_token_id)
            verification_data = db.execute(select_stmt).first()
            if verification_data is None:
                raise AuthError("Invalid API token")

            mfa_status, api_token_hash, api_token_expiration, cognito_id = (
                verification_data
            )

            # Check the API token hash
            try:
                ph.verify(api_token_hash, api_token_secret)
            except VerifyMismatchError:
                raise AuthError("Invalid API token")
            except (VerificationError, InvalidHash):
                raise AuthError("API token verification error")

            if ph.check_needs_rehash(api_token_hash):
                update_stmt = (
                    update(User)
                    .where(User.api_token_id == api_token_id)
                    .values(api_token_hash=ph.hash(api_token_secret))
                )
                db.execute(update_stmt)
                db.commit()

            # Check the API token expiration
            if (api_token_expiration is None) or (
                api_token_expiration.astimezone(utc) < datetime.now(utc)
            ):
                raise AuthError("API token is expired")
        finally:
            db.close()
    except Exception as e:
        raise AuthError(f"Database error {e}")

    if mfa_status != MFAStatus.enabled:
        raise AuthError("MFA is not enabled for this user")

    if cognito_id is None:
        raise AuthError("Cognito id is not found")

    # verify the user status
    if not _validate_user_status(cognito_id=cognito_id):
        raise AuthError("User is not approved")

    try:
        # Initialize the Cognito client with explicit short timeouts so a
        # stalled IDP call fails fast instead of consuming the Lambda budget.
        client = boto3.client("cognito-idp", config=_BOTO_TIMEOUT_CONFIG)
        # Get list users in the Cognito user pool with the specified Cognito ID
        response = client.list_users(
            UserPoolId=USER_POOL_ID, Filter=f'sub = "{cognito_id}"'
        )
        logger.info(len(response["Users"]))
        if len(response["Users"]) == 0:
            raise AuthError("Cognito user is not found")
        elif len(response["Users"]) > 1:
            raise AuthError("Cognito user is duplicated")
        else:
            return response["Users"][0]["Username"]
    except Exception as e:
        raise AuthError(f"Failed to list users from Cognito {e}")


@tracer.capture_method
def _generate_stage_resource_arn(resource: str) -> str:
    # Generate the stage resource ARN for the API Gateway
    # NOTE: Cached policies must cover all API resources and methods.
    # Reference: https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html
    arn_parts = resource.split(":")

    if len(arn_parts) != 6:
        raise AuthError(f"Invalid methodArn: {resource}")

    region = arn_parts[3]
    account_id = arn_parts[4]

    api_gateway_parts = arn_parts[5].split("/")

    if len(api_gateway_parts) < 2:
        raise AuthError(f"Invalid methodArn: {resource}")

    api_id = api_gateway_parts[0]
    stage = api_gateway_parts[1]

    generated_arn = f"arn:aws:execute-api:{region}:{account_id}:{api_id}/{stage}/*/*"
    logger.info(
        f"Generated stage resource ARN: {generated_arn} from methodArn: {resource}"
    )

    return generated_arn


def _generate_policy_allow(principal_id="", resource="", user_id=""):
    # Generate allow policy for the API Gateway
    auth_response = {"principalId": principal_id}

    if resource is not None:
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": _generate_stage_resource_arn(resource),
                }
            ],
        }
        auth_response["policyDocument"] = policy_document
        auth_response["context"] = {
            "user_id": user_id,
        }

    return auth_response


def _generate_policy_deny(principal_id="", resource="", user_id=""):
    # Generate deny policy for the API Gateway
    auth_response = {"principalId": principal_id}

    if resource is not None:
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": _generate_stage_resource_arn(resource),
                }
            ],
        }
        auth_response["policyDocument"] = policy_document
        auth_response["context"] = {
            "user_id": user_id,
        }

    return auth_response


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    method_arn = event["methodArn"]
    # Marker log so that, on a future timeout, we can tell init/import stall
    # (no marker) from handler-body stall (marker present, no later logs).
    logger.info("lambda_handler entered", extra={"method_arn": method_arn})
    headers_raw = event.get("headers", {})
    headers = {k.lower(): v for k, v in headers_raw.items()}
    user_id = None
    unknown_user_id = "unknown"

    try:
        if "q-api-token" in headers:
            # Get API token from headers
            _validate_headers_for_api_token(headers)
            # Verify API token
            user_id = _verify_api_token(headers["q-api-token"])
        elif "authorization" in headers:
            # Verify Cognito ID token
            user_id = _verify_id_token(headers["authorization"])
        else:
            logger.error("Unexpected header")
            policy_document = _generate_policy_deny(
                unknown_user_id, method_arn, unknown_user_id
            )
            return policy_document
        if not user_id:
            # Generate deny policy
            policy_document = _generate_policy_deny(
                unknown_user_id, method_arn, unknown_user_id
            )
            return policy_document
        else:
            # Generate allow policy
            policy_document = _generate_policy_allow(user_id, method_arn, user_id)
            logger.info(f"Authorization success {policy_document}")
            return policy_document
    except AuthError as e:
        logger.exception(f"Authentication/Authorization failed: {str(e)}")
        policy_document = _generate_policy_deny(
            unknown_user_id, method_arn, unknown_user_id
        )
        return policy_document
    except Exception as e:
        logger.exception(f"Unexpected error occurred: {str(e)}")
        policy_document = _generate_policy_deny(
            unknown_user_id, method_arn, unknown_user_id
        )
        return policy_document
