import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from oqtopus_cloud.common.auth import AuthError, resolve_identity
from oqtopus_cloud.user.conf import logger


class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("x-correlation-id")
        if os.getenv("ENV") == "local":
            logger.info("Running in local environment")
            corr_id = "local-correlation-id"
        if not corr_id:
            corr_id = request.scope["aws.context"].aws_request_id
        corr_id = str(corr_id)

        logger.set_correlation_id(corr_id)

        # NB: this runs OUTSIDE FastAPI's ExceptionMiddleware, so raising
        # HTTPException here would surface as a 500 (only ServerErrorMiddleware
        # is further out). Return an explicit Response for auth failures instead.
        try:
            identity = resolve_identity(request)
            request.state.user_id = identity.user_id
            request.state.user_pool_id = identity.user_pool_id
            request.state.region = identity.region
        except AuthError as e:
            # OIDC path: caller could not be authenticated/authorized.
            logger.warning(f"Authentication/authorization failed: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers={"X-Correlation-Id": corr_id},
            )
        except KeyError:
            # AWS path: the API Gateway authorizer context is missing.
            logger.error("No AWS event found in request scope")
            return JSONResponse(
                status_code=500,
                content={"detail": "No AWS event found in request scope"},
                headers={"X-Correlation-Id": corr_id},
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
