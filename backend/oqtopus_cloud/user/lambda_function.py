"""Entry point of the development application

This module is the entry point of the development application. It creates the FastAPI
"""

from fastapi import FastAPI
from mangum import (
    Mangum,
)
from starlette.middleware.cors import CORSMiddleware

from oqtopus_cloud.user.conf import logger, metrics, tracer
from oqtopus_cloud.user.middleware import CustomMiddleware
from oqtopus_cloud.user.routers import (
    devices as device_router,
)
from oqtopus_cloud.user.routers import (
    jobs as job_router,
)

app: FastAPI = FastAPI()

app.add_middleware(CustomMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
