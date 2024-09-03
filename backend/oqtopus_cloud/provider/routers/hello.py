from fastapi import (
    APIRouter,
)
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.hello import (
    HelloWorldResponse,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get("/hello", response_model=HelloWorldResponse)
@tracer.capture_method
def hello_world() -> HelloWorldResponse:
    """Returns a HelloWorldResponse object with the message "Hello World!!"

    Returns:
        HelloWorldResponse: An object containing the message "Hello World!!"
    """
    print(logger.get_correlation_id())
    logger.info("invoked hello_world()")
    return HelloWorldResponse(message="Hello World!!")


@router.get("/hello/{name}", response_model=HelloWorldResponse)
@tracer.capture_method
def hello_name(name: str) -> HelloWorldResponse:
    """Returns a HelloWorldResponse object with the message "Hello {name}!!"

    Args:
        name (str): The name to be included in the message

    Returns:
        HelloWorldResponse: An object containing the message "Hello {name}!!"
    """
    logger.info("invoked hello_name()")
    return HelloWorldResponse(message=f"Hello {name}!!")
