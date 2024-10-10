import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.model_util import model_to_schema_dict
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
def list_devices(
    db: Session = Depends(get_db),
) -> list[DeviceInfo] | ErrorResponse:
    try:
        logger.info("invoked list_devices")
        devices = db.query(Device).all()
        return [model_to_schema(device) for device in devices]
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/devices/{deviceId}",
    response_model=DeviceInfo,
    responses={404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_device(
    deviceId: str,
    db: Session = Depends(get_db),
) -> DeviceInfo | ErrorResponse:
    """_summary_

    Args:
        deviceId (str): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Returns:
        GetDeviceResponse: _description_
    """
    # TODO implement error handling
    try:
        device = db.query(Device).where(Device.id == deviceId).first()
        logger.info("invoked get_device")
        if device:
            response = model_to_schema(device)
            return response
        else:
            detail = f"deviceId={deviceId} is not found."
            logger.info(detail)
            return NotFoundErrorResponse(detail=detail)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(detail=str(e))


MAP_MODEL_TO_SCHEMA = {
    "id": "deviceId",
    "device_type": "deviceType",
    "status": "status",
    "restart_at": "restartAt",
    "pending_tasks": "nPendingTasks",
    "n_qubits": "nQubits",
    "n_nodes": "nNodes",
    "basis_gates": "basisGates",
    "instructions": "supportedInstructions",
    "calibration_data": "calibrationData",
    "calibrated_at": "calibratedAt",
    "description": "description",
}


def model_to_schema(model: Device) -> DeviceInfo:
    schema_dict = model_to_schema_dict(model, MAP_MODEL_TO_SCHEMA)

    # load as json if not None.
    if schema_dict["basisGates"]:
        schema_dict["basisGates"] = json.loads(schema_dict["basisGates"])
    if schema_dict["supportedInstructions"]:
        schema_dict["supportedInstructions"] = json.loads(
            schema_dict["supportedInstructions"]
        )
    if schema_dict["calibrationData"]:
        calibration_data_dict = json.loads(schema_dict["calibrationData"])
        schema_dict["calibrationData"] = CalibrationData(**calibration_data_dict)
    if schema_dict["restartAt"]:
        schema_dict["restartAt"] = schema_dict["restartAt"].astimezone(jst)
    if schema_dict["calibratedAt"]:
        schema_dict["calibratedAt"] = schema_dict["calibratedAt"].astimezone(jst)
    response = DeviceInfo(**schema_dict)
    return response
