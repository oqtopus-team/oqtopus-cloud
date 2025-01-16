import json
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
)
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
)
from uuid_extensions import uuid7
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.whitelist_user import whitelist_user
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)

from oqtopus_cloud.admin.schemas.whitelistUser import(
    WhitelistUsersDef
)

from . import LoggerRouteHandler

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


class BadRequest(Exception):
    def __init__(self, detail: str):
        self.detail = detail


@router.get(
    "/whitelist_users",
    response_model=list[WhitelistUsersDef],
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_whitelist_users(
    db: Session = Depends(get_db),
) -> WhitelistUsersDef | list | ErrorResponse:
    logger.info("invoked get_whitelist_user")
    try:
        model = db.get(whitelist_user)
        if model is None:
            return NotFoundErrorResponse("whitelist_user not found")
        whitelist_users = model_to_schema(model)
        if isinstance(whitelist_users, ValueError):
            logger.warning(str(whitelist_users))
            return NotFoundErrorResponse("whitelist_users not found")
        else:
            return whitelist_users
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


# MAP_MODEL_TO_SCHEMA = {
#     "id": "id",
#     "group_id": "group_id",
#     "email": "email",
#     "username": "username",
#     "organization": "organization",
#     "is_signup_completed": "is_signup_completed",
# }


# def model_to_schema(model: whitelist_user) -> WhitelistUsersDef | None:
 
#     return WhitelistUsersDef(
#         id=model.id,
#         group_id=model.group_id,
#         email=model.email,
#         username=model.username,
#         organization=model.organization,
#         is_signup_completed=model.is_signup_completed
#     )
