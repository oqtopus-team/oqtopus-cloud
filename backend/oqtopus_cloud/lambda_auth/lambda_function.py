import os
from datetime import datetime
from typing import Optional

import boto3
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError
from sqlalchemy import select, update
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.user import MFAStatus, User, UserStatus
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.lambda_auth.conf import logger

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

ph = PasswordHasher()


class AuthError(Exception):
    """Custom exception for authentication errors"""

    pass


def _validate_user_status(
    email: str | None = None, cognito_id: str | None = None
) -> bool:
    try:
        # Get a database session
        dbs = get_db()
        db = next(dbs)

        user = None
        # Get the user status from the database
        if email:
            stmt = select(User).where(
                User.email == email, User.userstatus == UserStatus.approved
            )
            user = db.execute(stmt).scalar()
            db.close()
        elif cognito_id:
            stmt = select(User).where(
                User.cognito_id == cognito_id, User.userstatus == UserStatus.approved
            )
            user = db.execute(stmt).scalar()
            db.close()
        else:
            raise AuthError("email or cognito_id is not given")

        if user is None:
            logger.info(f"User {email} or {cognito_id} is not approved")
            return False
        # Get the MFA status from the database
        # only for the case from oqtopus-frontend
        if email and user.mfa_status != MFAStatus.enabled:
            raise AuthError("MFA is not enabled for this user")
        return True
    except Exception as e:
        logger.error(f"Failed to get user status: {e}")
        raise AuthError("Failed to get user status")


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
        jwks_client = jwt.PyJWKClient(jwks_url)
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
        if not _validate_user_status(email=token["cognito:username"]):
            raise AuthError("User is not approved")

        return token["cognito:username"]
    except Exception:
        raise AuthError("ID token is invalid")


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
        dbs = get_db()
        db = next(dbs)

        select_stmt = select(
            User.mfa_status,
            User.api_token_hash,
            User.api_token_expiration,
            User.cognito_id,
        ).where(User.api_token_id == api_token_id)
        verification_data = db.execute(select_stmt).first()
        if verification_data is None:
            raise AuthError("Invalid API token")

        mfa_status, api_token_hash, api_token_expiration, cognito_id = verification_data

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
        # Initialize the Cognito client
        client = boto3.client("cognito-idp")
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


def _generate_policy_allow(principal_id="", resource="", owner=""):
    # Generate allow policy for the API Gateway
    auth_response = {"principalId": principal_id}

    if resource is not None:
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": resource,
                }
            ],
        }
        auth_response["policyDocument"] = policy_document
        auth_response["context"] = {
            "owner": owner,
        }

    return auth_response


def _generate_policy_deny(principal_id="", resource="", owner=""):
    # Generate deny policy for the API Gateway
    auth_response = {"principalId": principal_id}

    if resource is not None:
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {"Action": "execute-api:Invoke", "Effect": "Deny", "Resource": resource}
            ],
        }
        auth_response["policyDocument"] = policy_document
        auth_response["context"] = {
            "owner": owner,
        }

    return auth_response


def lambda_handler(event, context):
    headers = event["headers"]
    method_arn = event["methodArn"]
    owner = None
    unknown_owner = "unknown"

    try:
        if "q-api-token" in headers:
            # Verify API token
            owner = _verify_api_token(headers["q-api-token"])
        elif "authorization" in headers:
            # Verify Cognito ID token
            owner = _verify_id_token(headers["authorization"])
        else:
            logger.error("Unexpected header")
            policy_document = _generate_policy_deny(
                unknown_owner, method_arn, unknown_owner
            )
            return policy_document
        if not owner:
            # Generate deny policy
            policy_document = _generate_policy_deny(
                unknown_owner, method_arn, unknown_owner
            )
            return policy_document
        else:
            # Generate allow policy
            policy_document = _generate_policy_allow(owner, method_arn, owner)
            logger.info(f"Authorization success {policy_document}")
            return policy_document
    except AuthError as e:
        logger.exception(f"Authentication/Authorization failed: {str(e)}")
        policy_document = _generate_policy_deny(
            unknown_owner, method_arn, unknown_owner
        )
        return policy_document
    except Exception as e:
        logger.exception(f"Unexpected error occurred: {str(e)}")
        policy_document = _generate_policy_deny(
            unknown_owner, method_arn, unknown_owner
        )
        return policy_document
