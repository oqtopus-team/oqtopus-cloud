from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import and_, asc, desc, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.announcements import Announcement
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.announcements import (
    GetAnnouncementResponse,
    GetAnnouncementsListResponse,
)
from oqtopus_cloud.user.schemas.errors import (
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/announcements",
    response_model=GetAnnouncementsListResponse,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_announcements_list(
    offset: Optional[int] = 0,
    limit: Optional[int] = 10,
    order: Optional[str] = None,
    current_time: Optional[str] = None,
    db: Session = Depends(get_db),
) -> GetAnnouncementsListResponse | ErrorResponse:
    try:
        logger.info("invoked get_announcements_list")

        arg_order = (
            desc(Announcement.start_time)
            if order == "DESC"
            else asc(Announcement.start_time)
        )

        stmt = (
            select(Announcement)
            .offset(offset)
            .limit(limit)
            .order_by(arg_order, Announcement.id)
        )

        if current_time is not None:
            ctime = datetime.fromisoformat(current_time).astimezone(utc)
            stmt = stmt.filter(
                and_(Announcement.start_time <= ctime, Announcement.end_time >= ctime)
            )

        announcements_list = db.scalars(stmt).all()
        return GetAnnouncementsListResponse(
            announcements=[
                model_to_schema(announcement) for announcement in announcements_list
            ]
        )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/announcements/{announcement_id}",
    response_model=GetAnnouncementResponse,
    responses={404: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def get_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
) -> GetAnnouncementResponse | ErrorResponse:
    try:
        logger.info("invoked get_announcement")
        announcement = db.scalars(
            select(Announcement).where(Announcement.id == announcement_id)
        ).first()
        if announcement:
            return model_to_schema(announcement)
        else:
            message = f"announcement_id={announcement_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def model_to_schema(model: Announcement) -> GetAnnouncementResponse:
    dict = {
        "id": getattr(model, "id", None),
        "title": getattr(model, "title", None),
        "content": getattr(model, "content", None),
        "start_time": getattr(model, "start_time", None),
        "end_time": getattr(model, "end_time", None),
        "publishable": getattr(model, "publishable", None),
    }
    return GetAnnouncementResponse.model_validate(dict)
