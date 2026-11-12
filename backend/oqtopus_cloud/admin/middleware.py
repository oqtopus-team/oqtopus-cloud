import asyncio
import os
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from oqtopus_cloud.admin.conf import logger
from oqtopus_cloud.common.auth import AuthError, AuthorizationError
from oqtopus_cloud.common.auth.admin import resolve_admin_identity


class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("x-correlation-id")
        if os.getenv("ENV") == "local":
            logger.info("Running in local environment")
            corr_id = "local-correlation-id"
        if not corr_id:
            # On AWS the Lambda context carries a request id; off AWS (e.g.
            # on-prem behind nginx, which does not add X-Correlation-Id) it is
            # absent, so fall back to a generated id rather than raising
            # KeyError before auth even runs.
            aws_context = request.scope.get("aws.context")
            corr_id = getattr(aws_context, "aws_request_id", None) or str(uuid.uuid4())
        corr_id = str(corr_id)

        logger.set_correlation_id(corr_id)

        # Identity resolution does blocking work in oidc mode (JWKS fetch + JWT
        # signature verify); offload it so it never blocks the event loop (which
        # would serialize concurrent requests on a long-running ASGI server).
        #
        # NB: this runs OUTSIDE FastAPI's ExceptionMiddleware, so raising an
        # HTTPException here would surface as a 500. Return explicit Responses
        # for auth failures instead (401 vs 403).
        try:
            identity = await asyncio.to_thread(resolve_admin_identity, request)
            request.state.user_id = identity.user_id
            request.state.user_pool_id = identity.user_pool_id
            request.state.region = identity.region
            request.state.auth_method = identity.auth_method
        except AuthorizationError as e:
            # Authenticated but not permitted (e.g. missing admin role) -> 403.
            logger.warning(f"Authorization failed: {e}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden"},
                headers={"X-Correlation-Id": corr_id},
            )
        except AuthError as e:
            # Authentication failed (missing/invalid token) -> 401.
            logger.warning(f"Authentication failed: {e}")
            headers = {"X-Correlation-Id": corr_id}
            if e.challenge:
                headers["WWW-Authenticate"] = e.challenge
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers=headers,
            )
        except KeyError:
            # aws mode: the API Gateway authorizer context is missing.
            logger.error("No AWS event found in request scope")
            return JSONResponse(
                status_code=500,
                content={"detail": "No AWS event found in request scope"},
                headers={"X-Correlation-Id": corr_id},
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
