import json
import os
from typing import (
    Any,
    Generator,
)

import boto3

# from aws_xray_sdk.core import xray_recorder
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
)
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import sessionmaker

# Per-call timeouts so a stalled AWS API raises a Python exception
# (visible in CloudWatch + X-Ray) instead of consuming the Lambda timeout
# budget and being SIGKILL'd. Normal Secrets Manager latency is ~40-50ms;
# read_timeout=3s gives ~60x headroom and with total_max_attempts=2 (one
# initial + one retry) the worst case is ~7s (3s read + 1s backoff + 3s
# read), well under the Lambda timeout. connect_timeout=2s bounds the
# TCP+TLS handshake.
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
# MySQL connect_timeout (seconds) passed to PyMySQL. Normal RDS Proxy
# connect latency is ~50-90ms; 5s is generous enough to ride out a brief
# credential-refresh window on the proxy while still failing fast on a
# true stall (default OS TCP timeout is ~75s, way too long).
_DB_CONNECT_TIMEOUT_SECONDS = 5
# MySQL read_timeout (seconds). connect_timeout only bounds establishing the
# socket; without read_timeout a query that stalls AFTER connect (RDS Proxy
# pinning, failover, max_connections wait) hangs unbounded and the Lambda is
# SIGKILL'd at its 15s limit with no log -- exactly the silent timeout we are
# trying to make traceable. Authorizer queries are single indexed lookups
# (~tens of ms), so 5s is ~100x headroom while still failing fast.
_DB_READ_TIMEOUT_SECONDS = 5


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
        config=_BOTO_TIMEOUT_CONFIG,
    )
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        raise e

    secret = get_secret_value_response["SecretString"]
    return json.loads(secret)


def get_db() -> Generator:
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
        connect_args={
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'",
            "connect_timeout": _DB_CONNECT_TIMEOUT_SECONDS,
            "read_timeout": _DB_READ_TIMEOUT_SECONDS,
        },
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


def get_cognito_client():
    region = None
    if os.getenv("ENV") == "local":
        region = "ap-northeast-1"
    else:
        user_pool_id = os.getenv("CLIENT_COGNITO_USER_POOL_ID")
        if user_pool_id:
            region = user_pool_id.split("_")[0]

    return boto3.client("cognito-idp", region_name=region)
