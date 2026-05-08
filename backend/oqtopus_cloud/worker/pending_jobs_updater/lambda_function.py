import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent, event_source
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel
from sqlalchemy import (
    and_,
    func,
    or_,
    select,
)

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.worker.pending_jobs_updater.conf import logger


class BaseResponse(BaseModel):
    statusCode: int
    body: str


class Response:
    @staticmethod
    def success(data: Any, status_code: int = 200) -> dict[str, Any]:
        """
        Generate success response
        :param data: response body data converted to json
        :param status_code: HTTP status code(default: 200)
        :return: dict for response
        """
        response = BaseResponse(
            statusCode=status_code,
            body=json.dumps(data),
        )
        return response.model_dump()

    @staticmethod
    def error(message: str, status_code: int = 500) -> dict[str, Any]:
        """
        Generate error response
        :param message: error message
        :param status_code: HTTP status code(default: 500)
        :return: dict for response
        """
        error_body = {"error": message}
        response = BaseResponse(
            statusCode=status_code,
            body=json.dumps(error_body),
        )
        return response.model_dump()


@event_source(data_class=EventBridgeEvent)
def lambda_handler(event: EventBridgeEvent, context):
    logger.info("invoke worker lambda_handler")
    try:
        db = next(get_db())
        response = update_pending_jobs(db)
        return response
    except Exception as e:
        logger.exception("Error occurred")
        return Response.error(str(e))


def update_pending_jobs(db):
    logger.info("invoked update_pending_jobs")
    devices = db.scalars(select(Device)).all()
    device_ids = [device.id for device in devices]
    since = parse_since(os.environ["COUNT_PENDING_JOBS_SINCE"])
    logger.info(f"device list is {device_ids}")
    for device_id in device_ids:
        n_pending_jobs = db.execute(
            select(func.count()).where(
                and_(
                    or_(
                        Job.status == "submitted",
                        Job.status == "ready",
                        Job.status == "running",
                    ),
                    Job.device_id == device_id,
                    Job.submitted_at >= since,
                )
            )
        ).scalar_one()
        logger.info(f"n_pending_jobs of device {device_id} is {n_pending_jobs}")
        device = db.get(Device, device_id)
        if device is None:
            body = json.dumps({"massage": f"device {device} not found error"})
            return Response.error(body)
        else:
            device.pending_jobs = n_pending_jobs
    db.commit()
    logger.info("finish update_pending_jobs")
    body = json.dumps({"message": "update_pending_jobs process is succeeded"})
    return Response.success(body)


def parse_since(since_str: str) -> datetime:
    units = {
        "second": "seconds",
        "seconds": "seconds",
        "sec": "seconds",
        "minute": "minutes",
        "minutes": "minutes",
        "min": "minutes",
        "hour": "hours",
        "hours": "hours",
        "h": "hours",
        "day": "days",
        "days": "days",
        "d": "days",
        "week": "weeks",
        "weeks": "weeks",
        "month": "months",
        "months": "months",
        "year": "years",
        "years": "years",
    }

    m = re.fullmatch(r"(\d+)\s*([a-zA-Z]+)", since_str.strip())
    if not m:
        raise ValueError(f"Invalid since format: {since_str!r}")

    amount, unit = int(m.group(1)), m.group(2).lower()
    if unit not in units:
        raise ValueError(f"Unknown unit: {unit!r}")

    delta = relativedelta(**{units[unit]: amount})
    return datetime.now(tz=timezone.utc) - delta
