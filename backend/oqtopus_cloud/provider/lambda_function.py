"""Entry point of the development application

This module is the entry point of the development application. It creates the FastAPI
"""

import os

import setuptools._distutils.util
from fastapi import FastAPI
from mangum import (
    Mangum,
)
from oqtopus_cloud.common.tracing import force_flush as _otel_force_flush
from oqtopus_cloud.common.tracing import setup_tracing
from oqtopus_cloud.provider.conf import logger, metrics, tracer
from oqtopus_cloud.provider.middleware import CustomMiddleware
from oqtopus_cloud.provider.routers import (
    devices as device_router,
)
from oqtopus_cloud.provider.routers import (
    hello as hello_router,
)
from oqtopus_cloud.provider.routers import (
    jobs as job_router,
)
from starlette.middleware.cors import CORSMiddleware

app: FastAPI = FastAPI()

app.add_middleware(CustomMiddleware)

ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "").split(",")
ALLOW_CREDENTIALS = setuptools._distutils.util.strtobool(
    os.getenv("ALLOW_CREDENTIALS", "false")
)
ALLOW_METHODS = os.getenv("ALLOW_METHODS", "").split(",")
ALLOW_HEADERS = os.getenv("ALLOW_HEADERS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOW_METHODS,
    allow_headers=ALLOW_HEADERS,
)

# Install OpenTelemetry instrumentation last so the tracing middleware wraps
# all other middleware in the request/response cycle.
setup_tracing(app, "oqtopus-cloud-provider")

app.include_router(
    hello_router.router,
    tags=["hello"],
)
app.include_router(
    device_router.router,
    tags=["device"],
)
app.include_router(
    job_router.router,
    tags=["job"],
)

handler: Mangum = Mangum(
    app,
    lifespan="off",
)
# mypy: disable-error-code = attr-defined
handler.__name__ = "handler"
handler = tracer.capture_lambda_handler(handler)
handler = logger.inject_lambda_context(handler, clear_state=True)
handler = metrics.log_metrics(handler)

_inner_handler = handler


def handler(event, context):  # type: ignore[no-redef]
    try:
        return _inner_handler(event, context)
    finally:
        _otel_force_flush()
