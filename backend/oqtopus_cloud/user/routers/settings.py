from os import environ
from fastapi import APIRouter

from oqtopus_cloud.user.common.settings import get_editable_fields, get_visible_fields
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    InternalServerErrorResponse,
    Message,
)
from oqtopus_cloud.user.schemas.settings import GetSettingsResponse

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/system/settings",
    response_model=GetSettingsResponse,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_settings() -> GetSettingsResponse | InternalServerErrorResponse:
    logger.info("invoked get system settings")

    try:
        allow_deletion = environ.get("ALLOW_DELETION", "false").upper() == "TRUE"
        editable_fields = get_editable_fields()
        visible_fields = get_visible_fields()
        login_history_enabled = (
            environ.get("LOGIN_HISTORY_ENABLED", "false").upper() == "TRUE"
        )

        return GetSettingsResponse(
            allow_deletion=allow_deletion,
            editable_fields=editable_fields,
            visible_fields=visible_fields,
            login_history_enabled=login_history_enabled,
        )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()
