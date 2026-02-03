from datetime import timedelta, datetime
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import asc, desc, select, and_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.announcements import (
    GetAnnouncementsListResponse,
    GetAnnouncementResponse,
    RegisterAnnouncementRequest,
    UpdateAnnouncementRequest,
)
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.admin.schemas.success import SuccessResponse
from oqtopus_cloud.common.models.announcements import Announcement
from oqtopus_cloud.common.session import (
    get_db,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)
utc = ZoneInfo("UTC")


@router.get(
    "/announcements",
    response_model=GetAnnouncementsListResponse,
    responses={
        500: {"model": Message},
    },
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
        logger.info("invoked get_announcements")

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

        query_result = db.scalars(stmt).all()
        announcements_list = [
            model_to_schema(announcement) for announcement in query_result
        ]
        return GetAnnouncementsListResponse(announcements=announcements_list)

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


@router.get(
    "/announcements/{announcement_id}",
    response_model=GetAnnouncementResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_announcement(
    announcement_id: str,
    db: Session = Depends(get_db),
) -> GetAnnouncementResponse | ErrorResponse:
    try:
        logger.info("invoked get_announcement")

        query_result = db.scalars(
            select(Announcement).where(Announcement.id == announcement_id)
        ).first()
        if query_result:
            announcement = model_to_schema(query_result)
            return announcement
        else:
            message = f"announcement_id={announcement_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(
                message=message,
                message_code="ANNOUNCEMENT_NOT_FOUND",
                message_params={"id": announcement_id},
            )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


@router.post(
    "/announcements",
    response_model=SuccessResponse,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def register_announcements(
    announcement_def: RegisterAnnouncementRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked register_announcement")

        announcement = Announcement(
            title=announcement_def.title,
            content=announcement_def.content,
            start_time=ensure_timezone(announcement_def.start_time),
            end_time=ensure_timezone(announcement_def.end_time),
            publishable=announcement_def.publishable,
        )
        db.add(announcement)
        db.commit()

        return SuccessResponse(
            message="Announcement registered successfully",
            message_code="ANNOUNCEMENT_REGISTERED",
        )

    except ValueError as e:
        logger.error(str(e))
        return BadRequestErrorResponse(
            message=str(e), message_code="INVALID_ANNOUNCEMENT_DATA"
        )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


@router.patch(
    "/announcements/{announcement_id}",
    response_model=SuccessResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_announcements_data(
    announcement_id: str,
    announcement_update: UpdateAnnouncementRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked update announcement data")

        stmt = select(Announcement).where(Announcement.id == announcement_id)
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            message = f"announcement_id={announcement_id} is not found."
            logger.error(message)
            return NotFoundErrorResponse(
                message=message,
                message_code="ANNOUNCEMENT_NOT_FOUND",
                message_params={"id": announcement_id},
            )

        update_fields = announcement_update.model_dump(exclude_none=True)

        for field, value in update_fields.items():
            if field == "start_time" or field == "end_time":
                value = ensure_timezone(value)
            setattr(query_result, field, value)
        db.commit()

        return SuccessResponse(
            message="Announcement updated successfully",
            message_code="ANNOUNCEMENT_UPDATED",
        )

    except ValueError as e:
        logger.error(str(e))
        return BadRequestErrorResponse(
            message=str(e), message_code="INVALID_ANNOUNCEMENT_DATA"
        )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


@router.delete(
    "/announcements/{announcement_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_announcement(
    announcement_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked delete announcement")

        query_result = (
            db.execute(select(Announcement).where(Announcement.id == announcement_id))
            .scalars()
            .first()
        )
        if not query_result:
            message = f"announcement_id={announcement_id} is not found."
            logger.error(message)
            return NotFoundErrorResponse(
                message=message,
                message_code="ANNOUNCEMENT_NOT_FOUND",
                message_params={"id": announcement_id},
            )

        db.delete(query_result)
        db.commit()

        return SuccessResponse(
            message="Announcement deleted successfully",
            message_code="ANNOUNCEMENT_DELETED",
        )

    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


# TODO: make it common function (announcement and devices)
def ensure_timezone(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utc)
    if dt.utcoffset() != timedelta(0):
        raise ValueError("Datetime is not in UTC.")
    return dt


def model_to_schema(model: Announcement) -> GetAnnouncementResponse:
    dict = {
        "id": model.id,
        "title": model.title,
        "content": model.content,
        "start_time": ensure_timezone(model.start_time),
        "end_time": ensure_timezone(model.end_time),
        "publishable": model.publishable,
        "updated_at": ensure_timezone(model.updated_at),
    }
    return GetAnnouncementResponse.model_validate(dict)
