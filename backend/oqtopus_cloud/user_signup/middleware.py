import os
import uuid

from fastapi import Request
from fastapi.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from oqtopus_cloud.user_signup.conf import logger


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

        logger.set_correlation_id(corr_id)

        try:
            if os.getenv("ENV") == "local":
                request.state.pool_id = "ap-northeast-1_1110A6PLE"
                request.state.client_id = "1h57kf5cpq17m0eml12EXAMPLE"
            else:
                request.state.pool_id = os.getenv("AUTH_USER_POOL_ID")
                request.state.client_id = os.getenv("USER_POOL_WEB_CLIENT_ID")

        except Exception as e:
            logger.error("Error while setting client_id", exc_info=e)
            raise HTTPException(
                status_code=500, detail="No AWS event found in request scope"
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
