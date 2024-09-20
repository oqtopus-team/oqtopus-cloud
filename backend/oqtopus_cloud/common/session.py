import json
import os
from typing import (
    Any,
    Generator,
)

import boto3

# from aws_xray_sdk.core import xray_recorder
from botocore.exceptions import (
    ClientError,
)
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import Session, sessionmaker


def get_secret() -> Any:
    """
    Retrieves the secret from the AWS Secrets Manager.

    Raises:
      ClientError: If there is an error while retrieving the secret.

    Returns:
      Any: The secret retrieved from the AWS Secrets Manager.
    """
    if os.environ.get("ENV") == "local":
        return {
            "username": "admin",
            "password": "password",
        }
    secret_name = os.environ["SECRET_NAME"]
    region = os.environ["AWS_REGION"]
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name=region,
    )
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e

    secret = get_secret_value_response["SecretString"]
    return json.loads(secret)


def get_db() -> Generator[Session, None, None]:
    """Returns a database session.

    This function creates a database session using the SQLAlchemy engine and sessionmaker.
    The session is then yielded to the caller, allowing them to perform database operations.
    If an exception occurs during the database operation, the session is rolled back and the exception is raised.
    Finally, the session is closed.

    Yields:
        Generator: A database session.

    Raises:
        Exception: If an exception occurs during the database operation.

    Returns:
        Generator: A database session.
    """
    secret = get_secret()
    host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
    connector = os.environ["DB_CONNECTOR"]
    SQLALCHEMY_DATABASE_URL = (
        f"{connector}://{secret['username']}:{secret['password']}@{host}/{db_name}"
    )

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
    )
    SessionLocal = sessionmaker(
        autoflush=False,
        bind=engine,
    )

    db = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()
