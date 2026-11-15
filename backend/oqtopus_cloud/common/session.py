import json
import os
from threading import Lock
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
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from oqtopus_cloud.common.db_tls import ssl_connect_args
from oqtopus_cloud.common.secret_file import load_secret_json

# Database connectors allowed at runtime. The connector is part of the SQLAlchemy
# URL (``<connector>://user:pass@host/db``), so an unexpected value would silently
# change the driver -- pin it to the one the stack is built and tested against.
ALLOWED_DB_CONNECTORS = frozenset({"mysql+pymysql"})

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

_DEFAULT_DB_POOL_SIZE = 5
_DEFAULT_DB_MAX_OVERFLOW = 0
_DEFAULT_DB_POOL_TIMEOUT_SECONDS = 30
_ENGINE_CACHE_LOCK = Lock()
_ENGINE_CACHE: dict[
    int | None,
    tuple[
        tuple[URL, int | None, int, int, float],
        Engine,
        sessionmaker[Session],
    ],
] = {}


# The credential source is an explicit switch, NOT inferred from the presence of
# a file path: a typo'd or missing DB_SECRET_FILE must fail, never silently fall
# back to local defaults or AWS Secrets Manager (that would be fail-open).
DB_CREDENTIAL_SOURCES = ("file", "local", "aws")


def db_credential_source() -> str:
    """Return the DB credential source: ``file`` | ``local`` | ``aws``.

    Driven by ``DB_CREDENTIAL_SOURCE``. When unset it defaults
    backward-compatibly (``local`` if ``ENV=local`` else ``aws``) so existing
    AWS/local deployments are unchanged. An unknown value is rejected.
    """
    src = os.environ.get("DB_CREDENTIAL_SOURCE")
    if src:
        normalized = src.strip().lower()
        if normalized not in DB_CREDENTIAL_SOURCES:
            raise RuntimeError(
                f"DB_CREDENTIAL_SOURCE={src!r} is invalid; "
                f"expected one of {DB_CREDENTIAL_SOURCES}"
            )
        return normalized
    return "local" if os.environ.get("ENV") == "local" else "aws"


def _require_db_secret_shape(data: Any, path: str) -> dict:
    """Validate the parsed secret has non-empty string username/password."""
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not (isinstance(username, str) and username and isinstance(password, str) and password):
        raise RuntimeError(
            f"DB secret file {path} must contain JSON with non-empty string "
            '"username" and "password" fields'
        )
    return {"username": username, "password": password}


def _db_secret_from_file() -> dict:
    """Load DB credentials from the restricted file (``DB_CREDENTIAL_SOURCE=file``).

    Fail-closed: a missing ``DB_SECRET_FILE``, an insecure/missing file, invalid
    JSON, or a bad shape all raise -- there is no fallback to another source. The
    password is never logged.
    """
    path = os.environ.get("DB_SECRET_FILE")
    if not path:
        raise RuntimeError("DB_CREDENTIAL_SOURCE=file requires DB_SECRET_FILE to be set")
    return _require_db_secret_shape(load_secret_json(path), path)


def validate_db_runtime_config() -> None:
    """Fail fast (at startup / before a DB command) on a misconfigured DB contract.

    Checks that ``DB_HOST`` / ``DB_NAME`` / ``DB_CONNECTOR`` are present and that
    the connector is on the allowlist, and -- in ``file`` credential mode -- that
    the secret file is present, secure, valid JSON, and well-shaped. This way a
    missing mount or a typo aborts startup instead of surfacing on the first
    request. The DB password is never logged by this check.

    Raises:
        RuntimeError: for a missing variable, a disallowed connector, an invalid
        ``DB_CREDENTIAL_SOURCE``, or a missing/malformed secret file
        (InsecureSecretFile / FileNotFoundError also propagate from the loader).
    """
    missing = [v for v in ("DB_HOST", "DB_NAME", "DB_CONNECTOR") if not os.environ.get(v)]
    if missing:
        raise RuntimeError(
            f"missing required DB configuration: {', '.join(missing)}"
        )
    connector = os.environ["DB_CONNECTOR"]
    if connector not in ALLOWED_DB_CONNECTORS:
        raise RuntimeError(
            f"DB_CONNECTOR={connector!r} is not allowed; "
            f"expected one of {sorted(ALLOWED_DB_CONNECTORS)}"
        )
    if db_credential_source() == "file":
        _db_secret_from_file()  # raises on missing/insecure/malformed


def get_secret() -> Any:
    """
    Retrieves the database credentials from the configured source.

    Source is ``db_credential_source()``:
        - ``file`` -> ``{"username", "password"}`` JSON from the restricted
        ``DB_SECRET_FILE`` (on-prem; same file-secret contract as the ops CLI).
        Fail-closed: no fallback to local/AWS.
        - ``local`` -> developer env vars (``DB_USERNAME`` / ``DB_PASSWORD``).
        - ``aws`` -> AWS Secrets Manager.

    Raises:
        ClientError: If there is an error while retrieving the secret from AWS.
        RuntimeError / InsecureSecretFile / FileNotFoundError: for a bad config or
        an unsafe/missing/malformed secret file.

    Returns:
        Any: The retrieved database credentials (``{"username", "password"}``).
    """
    source = db_credential_source()
    if source == "file":
        return _db_secret_from_file()
    if source == "local":
        return {
            "username": os.environ.get("DB_USERNAME", "admin"),
            "password": os.environ.get("DB_PASSWORD", "password"),
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


def build_db_url() -> URL:
    """Build the SQLAlchemy URL from DB config + resolved credentials.

    Uses ``URL.create()`` so credentials carrying URL-significant characters
    (``@ : / %``) are passed as components, never interpolated into a URL string
    (where e.g. ``p@ss`` would be parsed as password ``p`` and host ``ss@...``).
    ``DB_HOST`` may carry a ``host:port``; the port is split out so it is not
    glued onto the host. Shared by the application (:func:`_create_session`) and
    Alembic (``alembic/env.py``) so both reach the database identically.
    """
    connector = os.environ["DB_CONNECTOR"]
    raw_host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
    creds = get_secret()
    host, _, port = raw_host.partition(":")
    return URL.create(
        connector,
        username=creds["username"],
        password=creds["password"],
        host=host,
        port=int(port) if port else None,
        database=db_name,
    )


def _get_pool_settings() -> tuple[int, int, float]:
    pool_size = int(os.getenv("DB_POOL_SIZE", str(_DEFAULT_DB_POOL_SIZE)))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", str(_DEFAULT_DB_MAX_OVERFLOW)))
    pool_timeout = float(
        os.getenv(
            "DB_POOL_TIMEOUT_SECONDS",
            str(_DEFAULT_DB_POOL_TIMEOUT_SECONDS),
        )
    )
    if pool_size < 1:
        raise ValueError("DB_POOL_SIZE must be at least 1")
    if max_overflow < 0:
        raise ValueError("DB_MAX_OVERFLOW must be non-negative")
    if pool_timeout <= 0:
        raise ValueError("DB_POOL_TIMEOUT_SECONDS must be positive")
    return pool_size, max_overflow, pool_timeout


def _get_session_factory(
    database_url: URL,
    read_timeout: int | None,
    connect_args: dict[str, Any],
) -> sessionmaker[Session]:
    """Return a bounded, process-shared session factory.

    The authorizer has a separate read timeout from normal API and worker
    queries, so keep one shared Engine for each timeout variant.
    """
    pool_size, max_overflow, pool_timeout = _get_pool_settings()
    cache_key = (
        database_url,
        read_timeout,
        pool_size,
        max_overflow,
        pool_timeout,
    )
    with _ENGINE_CACHE_LOCK:
        cached = _ENGINE_CACHE.get(read_timeout)
        if cached is not None and cached[0] == cache_key:
            return cached[2]
        if cached is not None:
            cached[1].dispose()

        engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_pre_ping=True,
        )
        session_local = sessionmaker[Session](
            autoflush=False,
            bind=engine,
        )
        _ENGINE_CACHE[read_timeout] = (cache_key, engine, session_local)
        return session_local


def _dispose_cached_engines() -> None:
    """Dispose cached Engines; intended for tests and controlled reconfiguration."""
    with _ENGINE_CACHE_LOCK:
        for _, engine, _ in _ENGINE_CACHE.values():
            engine.dispose()
        _ENGINE_CACHE.clear()


def _create_session(read_timeout: int | None = None) -> Session:
    """Build and return a session backed by a shared database Engine.

    read_timeout (seconds) is the PyMySQL read_timeout and is passed ONLY by the
    authorizer (AUTH_DB_READ_TIMEOUT_SECONDS). It is intentionally NOT a parameter
    of the get_db FastAPI dependency -- see get_db for why.
    """
    url = build_db_url()
    connect_args: dict[str, Any] = {
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'",
        "connect_timeout": _DB_CONNECT_TIMEOUT_SECONDS,
    }
    if read_timeout is not None:
        connect_args["read_timeout"] = read_timeout
    # RDS Proxy rejects non-TLS connections once caching_sha2_password /
    # require_tls is enabled. Shared with alembic/env.py so both reach the
    # database the same way.
    connect_args.update(ssl_connect_args(url.host))
    session_local = _get_session_factory(
        url,
        read_timeout,
        connect_args,
    )
    return session_local()


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
