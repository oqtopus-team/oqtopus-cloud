import json

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.job import Job
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.worker.conf import logger
from sqlalchemy import (
    and_,
    func,
    or_,
    select,
)


def lambda_handler(event, context):
    # This lambda function is triggered from Amazon EventBridge periodically(e.g. 1min)
    # argument 'event' expects to have 'function' field and its value is identifier of process.
    logger.info("invoke worker lambda_handler")
    try:
        func = event["function"]
    except Exception:
        return {
            "statusCode": 400,
            "body": json.dumps(
                "Parse event argument is failed. Input body must have 'function' field."
            ),
        }

    match func:
        case "update_pending_jobs":
            # get DB session
            db = get_session()
            return update_pending_jobs(db)
        case _:
            return {"statusCode": 400, "body": json.dumps(f"unknown function {func}")}


def get_session():
    return next(get_db())


def update_pending_jobs(db):
    try:
        logger.info("invoked update pending jobs")
        devices = db.scalars(select(Device)).all()
        device_ids = [device.id for device in devices]
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
                    )
                )
            ).scalar_one()
            logger.info(f"n_pending_jobs of device {device_id} is {n_pending_jobs}")
            device = db.get(Device, device_id)
            if device is None:
                return {"statusCode": 404, "body": json.dumps("not found error")}
            else:
                device.pending_jobs = n_pending_jobs
        db.commit()
        logger.info("finish update_pending_jobs")
        return {"statusCode": 200, "body": json.dumps("success response")}
    except Exception:
        return {"statusCode": 500, "body": json.dumps("internal server error")}
