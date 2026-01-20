import json

from fastapi import APIRouter, Depends
from fastapi import Request as Event
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.devices import (
    DeviceInfo,
)
from oqtopus_cloud.user.schemas.errors import (
    ErrorResponse,
    ForbiddenErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/devices", response_model=list[DeviceInfo], responses={500: {"model": Message}}
)
@tracer.capture_method
def get_devices(
    event: Event,
    db: Session = Depends(get_db),
) -> list[DeviceInfo] | ErrorResponse:
    try:
        logger.info("invoked list_devices")
        available_devices = get_user_available_devices(event.state.owner, db)

        if available_devices == "*":
            devices = db.scalars(select(Device)).all()
        else:
            devices = db.scalars(
                select(Device).where(Device.id.in_(available_devices))
            ).all()

        return [model_to_schema(device) for device in devices]
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/devices/{device_id}",
    response_model=DeviceInfo,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_device(
    device_id: str,
    event: Event,
    db: Session = Depends(get_db),
) -> DeviceInfo | ErrorResponse:
    """_summary_

    Args:
        device_id (str): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Returns:
        GetDeviceResponse: _description_
    """
    # TODO implement error handling
    try:
        user_identifier = event.state.owner
        logger.info(
            f"User {user_identifier} is trying to access device_id={device_id}."
        )
        available_devices = get_user_available_devices(user_identifier, db)

        if available_devices != "*" and device_id not in available_devices:
            logger.error(
                f"{user_identifier} is not allowed to access device_id={device_id}."
            )
            return ForbiddenErrorResponse(
                message=f"Cannot access device_id={device_id}."
            )

        device = db.scalars(select(Device).where(Device.id == device_id)).first()
        logger.info("invoked get_device")
        if device:
            response = model_to_schema(device)
            return response
        else:
            message = f"device_id={device_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


MAP_MODEL_TO_SCHEMA = {
    "id": "device_id",
    "device_type": "device_type",
    "status": "status",
    "available_at": "available_at",
    "pending_jobs": "n_pending_jobs",
    "n_qubits": "n_qubits",
    "basis_gates": "basis_gates",
    "instructions": "supported_instructions",
    "device_info": "device_info",
    "calibrated_at": "calibrated_at",
    "description": "description",
}


def model_to_schema(model: Device) -> DeviceInfo:
    dict = {
        "device_id": getattr(model, "id", None),
        "device_type": getattr(model, "device_type", None),
        "status": model.status,
        "available_at": getattr(model, "available_at", None),
        "n_pending_jobs": getattr(model, "pending_jobs", None),
        "n_qubits": getattr(model, "n_qubits", None),
        "basis_gates": json.loads(getattr(model, "basis_gates", "[]")),
        "supported_instructions": json.loads(getattr(model, "instructions", "[]")),
        "device_info": getattr(model, "device_info", None),
        "calibrated_at": getattr(model, "calibrated_at", None),
        "description": model.description,
    }
    return DeviceInfo.model_validate(dict)


def get_user_available_devices(user_identifier: str, db: Session) -> list[str] | str:
    try:
        user = db.scalars(
            select(User).where(User.user_identifier == user_identifier)
        ).first()
        if user is None or user.available_devices is None:
            return []

        if user.available_devices == "*":
            return user.available_devices

        available_devices = json.loads(user.available_devices)

        if isinstance(available_devices, list):
            return available_devices
        else:
            return []
    except Exception as e:
        logger.error(f"Failed to list available devices: {e}")
        return []
