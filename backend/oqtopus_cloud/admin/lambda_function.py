"""Entry point of the development application

This module is the entry point of the development application. It creates the FastAPI
"""

import os

import setuptools._distutils.util
from fastapi import FastAPI
from fastapi_pagination import add_pagination
from mangum import (
    Mangum,
)
from starlette.middleware.cors import CORSMiddleware

from oqtopus_cloud.admin.conf import logger, metrics, tracer
from oqtopus_cloud.admin.middleware import CustomMiddleware
from oqtopus_cloud.admin.routers import (
    devices as devices_router,
)
from oqtopus_cloud.admin.routers import (
    users as users_router,
)
from oqtopus_cloud.admin.routers import (
    whitelist_users as whitelist_router,
)

app: FastAPI = add_pagination(FastAPI())

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
    users_router.router,
    tags=["user"],
)

app.include_router(
    whitelist_router.router,
    tags=["whitelist"],
)

app.include_router(
    devices_router.router,
    tags=["device"],
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
