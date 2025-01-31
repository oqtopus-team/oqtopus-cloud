import jwt
from sqlalchemy import select
from typing import Optional
import os
import boto3
from datetime import datetime
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.lambda_auth.conf import logger
from oqtopus_cloud.common.session import get_db


def _verify_id_token(id_token: Optional[str]) -> str:
    if id_token is None:
        logger.error("ID token is None")
        raise Exception("Internal Server Error")

    id_token = id_token.replace("Bearer ", "")

    # Get environment variables
    try:
        REGION = os.environ["REGION"]
        USER_POOL_ID = os.environ["AUTH_USER_POOL_ID"]
        CLIENT_ID = os.environ["USER_POOL_WEB_CLIENT_ID"]
    except Exception as e:
        logger.error(f"Environment variable is not set {e}")
        raise Exception("Internal Server Error")

    # Construct the issuer and JWKS URL for the Cognito user pool
    issuer = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"
    jwks_url = f"{issuer}/.well-known/jwks.json"

    try:
        # Get the signing key from the JWT
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    except Exception as e:
        logger.error(f"Failed to get signing key from JWT: {e}")
        raise Exception("Internal Server Error")

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

        # verify the taken_use claim
        if token["token_use"] != "id":
            logger.error("ID token is invalid.")
            raise Exception("Internal Server Error")

        return token["cognito:username"]
    except Exception as e:
        logger.error(f"Failed to decode JWT: {e}")
        raise Exception("Internal Server Error")


def _verify_api_token(api_token: Optional[str]) -> str:
    if api_token is None or api_token == "":
        logger.error("API token is None")
        raise Exception("Internal Server Error")

    # Get environment variables
    try:
        USER_POOL_ID = os.environ["AUTH_USER_POOL_ID"]
    except Exception as e:
        logger.error(f"Environment variable is not set {e}")
        raise Exception("Internal Server Error")

    try:
        # Get a database session
        dbs = get_db()
        db = next(dbs)

        # Get the API token expiration from the database
        stmt_api_token_expiration = select(User.api_token_expiration).where(User.api_token_secret == api_token)
        api_token_expiration = db.execute(stmt_api_token_expiration).scalars().first()

        # Check the API token expiration
        if (api_token_expiration is None) or (api_token_expiration < datetime.now()):
            logger.error("API token is expired.")
            raise Exception("Internal Server Error")

        # Get the Cognito ID from the database
        stmt_cognito_id = select(User.cognito_id).where(User.api_token_secret == api_token)
        cognito_id = db.execute(stmt_cognito_id).scalars().first()
        db.close()
    except Exception as e:
        logger.error(f"Database error {e}")
        raise Exception("Internal Server Error")

    if cognito_id is None:
        logger.error("Cognito id is not found.")
        raise Exception("Internal Server Error")

    try:
        # Initialize the Cognito client
        client = boto3.client("cognito-idp")
        # Get list users in the Cognito user pool with the specified Cognito ID
        response = client.list_users(
            UserPoolId=USER_POOL_ID, Filter=f'sub = "{cognito_id}"'
        )

        return response["Users"][0]["Username"]
    except Exception as e:
        logger.error(f"Failed to list users from Cognito {e}")
        raise Exception("Internal Server Error")


def _generate_policy_allow(principal_id="", resource="", owner=""):
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

    if "q-api-token" in headers:
        # Verify API token
        try:
            owner = _verify_api_token(headers["q-api-token"])
        except Exception:
            policy_document = _generate_policy_deny(owner, method_arn, owner)
            return policy_document
    else:
        # Verify Cognito ID token
        try:
            owner = _verify_id_token(headers["authorization"])
        except Exception:
            policy_document = _generate_policy_deny(owner, method_arn, owner)
            return policy_document

    if owner is not None and owner != "":
        # Generate allow policy
        policy_document = _generate_policy_allow(owner, method_arn, owner)
        logger.info(f"Authorization success {policy_document}")
        return policy_document
    else:
        # Generate deny policy
        policy_document = _generate_policy_deny(owner, method_arn, owner)
        return policy_document
