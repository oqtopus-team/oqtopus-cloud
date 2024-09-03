import os

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEvent
from fastapi import Request
from fastapi.exceptions import HTTPException
from oqtopus_cloud.provider.conf import logger
from starlette.middleware.base import BaseHTTPMiddleware


class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("x-correlation-id")
        if os.getenv("ENV") == "local":
            logger.info("Running in local environment")
            corr_id = "local-correlation-id"
        if not corr_id:
            corr_id = request.scope["aws.context"].aws_request_id

        logger.set_correlation_id(corr_id)

        try:
            if os.getenv("ENV") == "local":
                request.state.apigateway_authorizer = {
                    "cognito:username": "admin",
                }
            else:
                event = APIGatewayProxyEvent(request.scope["aws.event"])
                request.state.apigateway_authorizer = event.request_context.authorizer
        except KeyError:
            logger.error("No AWS event found in request scope")
            raise HTTPException(
                status_code=500, detail="No AWS event found in request scope"
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
