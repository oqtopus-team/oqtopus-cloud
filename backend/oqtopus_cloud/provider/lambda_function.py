"""Entry point of the development application

This module is the entry point of the development application. It creates the FastAPI
"""

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
    jobs as task_router,
)
from starlette.middleware.cors import CORSMiddleware

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

handler: Mangum = Mangum(
    app,
    lifespan="off",
)
# mypy: disable-error-code = attr-defined
handler.__name__ = "handler"
handler = tracer.capture_lambda_handler(handler)
handler = logger.inject_lambda_context(handler, clear_state=True)
handler = metrics.log_metrics(handler)
