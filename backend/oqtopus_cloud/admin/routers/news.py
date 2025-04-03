from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.news import (
    GetNewsListResponse,
    GetNewsResponse,
    RegisterNewsRequest,
    UpdateNewsRequest,
)
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.admin.schemas.success import SuccessResponse
from oqtopus_cloud.common.models.news import News
from oqtopus_cloud.common.session import (
    get_db,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)
utc = ZoneInfo("UTC")


@router.get(
    "/news",
    response_model=GetNewsListResponse,
    responses={
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_news_list(
    offset: Optional[int] = 0, limit: Optional[int] = 10, db: Session = Depends(get_db)
) -> GetNewsListResponse | ErrorResponse:
    try:
        logger.info("invoked get_news")
        query_result = db.scalars(select(News).offset(offset).limit(limit)).all()
        news_list = [model_to_schema(news) for news in query_result]
        return GetNewsListResponse(news=news_list)

    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/news/{news_id}",
    response_model=GetNewsResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_news(
    news_id: str,
    db: Session = Depends(get_db),
) -> GetNewsResponse | ErrorResponse:
    try:
        logger.info("invoked get_news")

        query_result = db.scalars(select(News).where(News.id == news_id)).first()
        if query_result:
            news = model_to_schema(query_result)
            return news
        else:
            message = f"news_id={news_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)

    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.post(
    "/news",
    response_model=SuccessResponse,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def register_news(
    news_def: RegisterNewsRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked register_news")

        news = News(
            title=news_def.title,
            content=news_def.content,
            start_time=ensure_timezone(news_def.start_time),
            end_time=ensure_timezone(news_def.end_time),
            publishable=news_def.publishable,
        )
        db.add(news)
        db.commit()

        return SuccessResponse(message="News registered successfully")

    except ValueError as e:
        logger.error(str(e))
        return BadRequestErrorResponse(message=str(e))

    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.patch(
    "/news/{news_id}",
    response_model=SuccessResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_news_data(
    news_id: str,
    news_update: UpdateNewsRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked update news data")

        stmt = select(News).where(News.id == news_id)
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            message = f"news_id={news_id} is not found."
            logger.error(message)
            return NotFoundErrorResponse(message=message)

        update_fields = news_update.model_dump(exclude_none=True)
        for field, value in update_fields.items():
            setattr(query_result, field, value)
        db.commit()

        return SuccessResponse(message="News updated successfully")

    except Exception as e:
        tracer.put_annotation("db_error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/news/{news_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_news(
    news_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked delete news")

        query_result = (
            db.execute(select(News).where(News.id == news_id)).scalars().first()
        )
        if not query_result:
            message = f"news_id={news_id} is not found"
            logger.error(message)
            return NotFoundErrorResponse(message=message)

        db.delete(query_result)
        db.commit()

        return SuccessResponse(message="News deleted successfully")

    except Exception as e:
        tracer.put_annotation("db_error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


# TODO: make it common function (news and devices)
def ensure_timezone(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utc)
    if dt.utcoffset() != timedelta(0):
        raise ValueError("Datetime is not in UTC.")
    return dt


def model_to_schema(model: News) -> GetNewsResponse:
    dict = {
        "id": model.id,
        "title": model.title,
        "content": model.content,
        "start_time": ensure_timezone(model.start_time),
        "end_time": ensure_timezone(model.end_time),
        "publishable": model.publishable,
    }
    return GetNewsResponse.model_validate(dict)
