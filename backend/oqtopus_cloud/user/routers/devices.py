import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.devices import (
    DeviceInfo,
)
from oqtopus_cloud.user.schemas.errors import (
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/devices", response_model=list[DeviceInfo], responses={500: {"model": Detail}}
)
@tracer.capture_method
def get_devices(
    db: Session = Depends(get_db),
) -> list[DeviceInfo] | ErrorResponse:
    try:
        logger.info("invoked list_devices")
        devices = db.scalars(select(Device)).all()
        return [model_to_schema(device) for device in devices]
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/devices/{device_id}",
    response_model=DeviceInfo,
    responses={404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_device(
    device_id: str,
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
        device = db.scalars(select(Device).where(Device.id == device_id)).first()
        logger.info("invoked get_device")
        if device:
            response = model_to_schema(device)
            return response
        else:
            detail = f"device_id={device_id} is not found."
            logger.info(detail)
            return NotFoundErrorResponse(detail=detail)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(detail=str(e))


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
