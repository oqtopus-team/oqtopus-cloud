import os
from typing import Optional

import jwt
from sqlalchemy import select

from oqtopus_cloud.common.auth.api_token import (
    ApiTokenError,
    parse_api_token,
    rehash_api_token_if_needed,
    verify_api_token,
)
from oqtopus_cloud.common.auth.cognito_policy import (
    CognitoPolicyError,
    MfaNotEnabled,
    require_cognito_user_exists,
    require_mfa_enabled,
)
from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import AUTH_DB_READ_TIMEOUT_SECONDS, _create_session
from oqtopus_cloud.lambda_auth.conf import logger, tracer

# JWKS fetch timeout (seconds). The Cognito ListUsers call's timeouts live in
# common.auth.cognito_policy, which both this authorizer and the in-app resolver
# share so the AWS authorization checks cannot drift.
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
        # MFA must be enabled for the browser (access-token) path. Shared with
        # the in-app resolver via common.auth.cognito_policy.
        if user_id:
            require_mfa_enabled(user.mfa_status)
        return True
    except Exception as e:
        logger.error(f"Failed to get user status: {e}")
        raise AuthError("Failed to get user status")


@tracer.capture_method
def _verify_access_token(access_token: Optional[str]) -> str:
    if access_token is None:
        raise AuthError("Access token is not found")

    access_token = access_token.replace("Bearer ", "")

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
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
    except Exception as e:
        raise AuthError(f"Failed to get signing key from JWT: {e}")

    try:
        # Cognito access tokens identify the app client with ``client_id``;
        # unlike ID tokens, they don't necessarily contain an ``aud`` claim.
        token = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "require": [
                    "exp",
                    "iss",
                    "client_id",
                    "token_use",
                    "username",
                ],
                "verify_iss": True,
                "verify_exp": True,
                "verify_aud": False,
            },
        )

        if token["token_use"] != "access":
            raise AuthError("Invalid token_use")
        if token["client_id"] != CLIENT_ID:
            raise AuthError("Invalid client_id")

        # verify the user status
        if not _validate_user_status(user_id=token["username"]):
            raise AuthError("User is not approved")

        return token["username"]
    except Exception:
        raise AuthError("Access token is invalid")


@tracer.capture_method
def _verify_api_token(api_token: Optional[str]) -> str:
    # Parse via the shared parser so CLI and Lambda reject the same shapes.
    try:
        api_token_id, api_token_secret = parse_api_token(api_token)
    except ApiTokenError as e:
        raise AuthError(str(e))

    # Get environment variables
    try:
        USER_POOL_ID = os.environ["AUTH_USER_POOL_ID"]
    except Exception as e:
        raise AuthError(f"Environment variable is not set {e}")

    # Credential check (Argon2/expiry) is shared with the in-app resolver via
    # common.auth.api_token so the two cannot drift. Extract the values we need
    # and close the session immediately -- the authorization below includes a
    # Cognito call, and we must not hold an RDS Proxy connection across it.
    db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        user = verify_api_token(db, api_token_id, api_token_secret)
        mfa_status = user.mfa_status
        cognito_id = user.cognito_id
        current_hash = user.api_token_hash
    except ApiTokenError as e:
        raise AuthError(f"Database error {e}")
    except Exception as e:
        raise AuthError(f"Database error {e}")
    finally:
        db.close()

    # Authorization (no DB connection held across these). MFA + Cognito-user
    # existence are shared with the in-app resolver (common.auth.cognito_policy)
    # so the AWS checks cannot drift.
    try:
        require_mfa_enabled(mfa_status)
    except MfaNotEnabled as e:
        raise AuthError(str(e))

    if cognito_id is None:
        raise AuthError("Cognito id is not found")

    # verify the user status
    if not _validate_user_status(cognito_id=cognito_id):
        raise AuthError("User is not approved")

    try:
        cognito_user = require_cognito_user_exists(cognito_id, user_pool_id=USER_POOL_ID)
    except CognitoPolicyError as e:
        # Preserve the historical deny message (zero/duplicate/Cognito error).
        raise AuthError(f"Failed to list users from Cognito {e}")
    username = cognito_user["Username"]

    # Fully accepted -> opportunistic hash upgrade (never for a rejected req).
    # A fresh short-lived session, so no connection was held during the Cognito
    # call above.
    rehash_db = _create_session(read_timeout=AUTH_DB_READ_TIMEOUT_SECONDS)
    try:
        rehash_api_token_if_needed(
            rehash_db, api_token_id, current_hash, api_token_secret
        )
    finally:
        rehash_db.close()
    return username


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
            # Verify API token
            user_id = _verify_api_token(headers["q-api-token"])
        elif "authorization" in headers:
            # Verify the Cognito access token sent by the browser client.
            user_id = _verify_access_token(headers["authorization"])
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
