from typing import Callable

from aws_lambda_powertools.metrics import MetricUnit, single_metric
from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from oqtopus_cloud.provider.conf import logger
from starlette.exceptions import HTTPException as StarletteHTTPException


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

            def log_completion(status_code: int) -> None:
                # FastAPI collapses the handler outcome into the HTTP response,
                # so log the final status here; promote 5xx to error level so
                # swallowed server errors are no longer invisible in the logs.
                log = logger.error if status_code >= 500 else logger.info
                log("Request completed", extra={"status_code": status_code})

            try:
                response = await original_route_handler(request)
            except StarletteHTTPException as exc:
                # FastAPI raises HTTP/validation errors out of the route handler
                # for the app-level handlers to turn into responses; capture the
                # eventual status before re-raising.
                log_completion(exc.status_code)
                raise
            except RequestValidationError:
                log_completion(422)
                raise
            except Exception:
                log_completion(500)
                raise
            log_completion(response.status_code)
            return response

        return route_handler
