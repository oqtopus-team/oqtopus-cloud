from typing import Callable

from aws_lambda_powertools.metrics import MetricUnit, single_metric
from fastapi import Request, Response
from fastapi.routing import APIRoute

from oqtopus_cloud.user.conf import logger


class LoggerRouteHandler(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def route_handler(request: Request) -> Response:
            # Add fastapi context to logs
            ctx = {
                "path": request.url.path,
                "route": self.path,
                "method": request.method,
            }
            logger.append_keys(fastapi=ctx)
            logger.info("Received request")
            # Add count metric with method + route as dimenision
            with single_metric(
                name="RequestCount", unit=MetricUnit.Count, value=1
            ) as metric:
                metric.add_dimension(
                    name="route", value=f"{request.method} {self.path}"
                )

            return await original_route_handler(request)

        return route_handler
