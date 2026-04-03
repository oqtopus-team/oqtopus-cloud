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

from oqtopus_cloud.user_signup.conf import logger, metrics, tracer
from oqtopus_cloud.user_signup.middleware import CustomMiddleware
from oqtopus_cloud.user_signup.routers import (
    confirm_signup as confirm_signup_router,
)
from oqtopus_cloud.user_signup.routers import (
    mfa_reset as mfa_reset_router,
)
from oqtopus_cloud.user_signup.routers import (
    mfa_reset_request as mfa_reset_request_router,
)
from oqtopus_cloud.user_signup.routers import (
    signup as signup_router,
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
    signup_router.router,
    tags=["signup"],
)

app.include_router(
    confirm_signup_router.router,
    tags=["confirm"],
)

app.include_router(
    mfa_reset_request_router.router,
    tags=["mfa_reset_request"],
)

app.include_router(
    mfa_reset_router.router,
    tags=["mfa_reset"],
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
