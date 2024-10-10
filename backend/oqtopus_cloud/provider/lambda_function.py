"""Entry point of the development application

This module is the entry point of the development application. It creates the FastAPI
"""

import os

import setuptools._distutils.util
from fastapi import FastAPI
from mangum import (
    Mangum,
)
from oqtopus_cloud.provider.conf import logger, metrics, tracer
from oqtopus_cloud.provider.middleware import CustomMiddleware
from oqtopus_cloud.provider.routers import (
    devices as device_router,
)
from oqtopus_cloud.provider.routers import (
    hello as hello_router,
)
from oqtopus_cloud.provider.routers import (
    results as result_router,
)
from oqtopus_cloud.provider.routers import (
    tasks as task_router,
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

app.include_router(
    hello_router.router,
    tags=["hello"],
)
app.include_router(
    device_router.router,
    tags=["device"],
)
app.include_router(
    task_router.router,
    tags=["task"],
)
app.include_router(
    result_router.router,
    tags=["result"],
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
