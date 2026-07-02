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
from sqlalchemy.orm import Session, sessionmaker

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
# MySQL read_timeout (seconds) for the AUTHORIZER ONLY (passed explicitly via
# get_db(read_timeout=...)). connect_timeout only bounds establishing the
# socket; without read_timeout a query that stalls AFTER connect (RDS Proxy
# pinning, failover, max_connections wait) hangs unbounded and the Lambda is
# SIGKILL'd at its 15s limit with no log -- exactly the silent timeout we are
# trying to make traceable. Authorizer queries are single indexed lookups
# (~tens of ms), so 5s is ~100x headroom while still failing fast.
#
# NOT applied to the shared default: the worker (per-device COUNT aggregates)
# and list endpoints (paginate/scalars().all()) legitimately run longer than
# the authorizer and have larger Lambda budgets, so a global 5s read_timeout
# would turn previously-slow-but-successful queries into 500s / worker failures
# under the very same RDS Proxy conditions cited above. Those callers keep the
# original unbounded read behavior.
AUTH_DB_READ_TIMEOUT_SECONDS = 5


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


# Amazon RDS CA bundle shipped inside this package (see
# oqtopus_cloud/common/certs/global-bundle.pem). Used to verify the RDS Proxy
# server certificate when TLS is required. Overridable via the DB_SSL_CA env var
# (wired through Terraform), with this bundled copy as a safe fallback so a
# missing env var cannot silently drop TLS or cause an outage.
_DEFAULT_DB_SSL_CA = os.path.join(
    os.path.dirname(__file__), "certs", "global-bundle.pem"
)


def _create_session(read_timeout: int | None = None) -> Session:
    """Build and return a database session.

    read_timeout (seconds) is the PyMySQL read_timeout and is passed ONLY by the
    authorizer (AUTH_DB_READ_TIMEOUT_SECONDS). It is intentionally NOT a parameter
    of the get_db FastAPI dependency -- see get_db for why.
    """
    secret = get_secret()
    host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
    connector = os.environ["DB_CONNECTOR"]
    SQLALCHEMY_DATABASE_URL = (
        f"{connector}://{secret['username']}:{secret['password']}@{host}/{db_name}"
    )
    connect_args: dict[str, Any] = {
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'",
        "connect_timeout": _DB_CONNECT_TIMEOUT_SECONDS,
    }
    if read_timeout is not None:
        connect_args["read_timeout"] = read_timeout
    # RDS Proxy rejects non-TLS connections once caching_sha2_password /
    # require_tls is enabled, so verify the server cert against the RDS CA bundle.
    # Skipped for ENV=local, where the dev MySQL container is reached over a
    # trusted network and serves no CA-signed certificate.
    if os.environ.get("ENV") != "local":
        connect_args["ssl"] = {"ca": os.environ.get("DB_SSL_CA", _DEFAULT_DB_SSL_CA)}
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args=connect_args,
    )
    SessionLocal = sessionmaker(
        autoflush=False,
        bind=engine,
    )
    return SessionLocal()


def get_db() -> Generator:
    """FastAPI dependency that yields a database session.

    Kept parameter-less on purpose: FastAPI treats a dependency callable's
    parameters as request parameters, so adding e.g. read_timeout here would
    expose a client-controllable `read_timeout` query parameter on every
    Depends(get_db) endpoint. Callers that need a bounded read (the authorizer)
    call _create_session directly instead of going through this dependency.
    """
    db = _create_session()
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
