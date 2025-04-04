from datetime import datetime

from oqtopus_cloud.user.schemas.news import GetNewsResponse
from oqtopus_cloud.common.models.news import News
from oqtopus_cloud.user.schemas.news import GetNewsListResponse
import pytz
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
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
    "/news", response_model=GetNewsListResponse, responses={500: {"model": Message}}
)
@tracer.capture_method
def get_news_list(
    db: Session = Depends(get_db),
) -> GetNewsListResponse | ErrorResponse:
    try:
        logger.info("invoked list_news")
        news_list = db.scalars(select(News)).all()
        return GetNewsListResponse(news=[model_to_schema(news) for news in news_list])
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))


@router.get(
    "/news/{news_id}",
    response_model=GetNewsResponse,
    responses={404: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def get_news(
    news_id: int,
    db: Session = Depends(get_db),
) -> GetNewsResponse | ErrorResponse:
    try:
        news = db.scalars(select(News).where(News.id == news_id)).first()
        logger.info("invoked get_news")
        if news:
            return model_to_schema(news)
        else:
            message = f"news_id={news_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))


def localize(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return pytz.utc.localize(dt)


def model_to_schema(model: News) -> GetNewsResponse:
    dict = {
        "id": getattr(model, "id", None),
        "title": getattr(model, "title", None),
        "content": getattr(model, "content", None),
        "start_time": localize(getattr(model, "start_time", None)),
        "end_time": localize(getattr(model, "end_time", None)),
        "publishable": getattr(model, "publishable", None),
    }
    return GetNewsResponse.model_validate(dict)
