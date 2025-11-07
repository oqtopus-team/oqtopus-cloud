from enum import Enum

from fastapi import (
    APIRouter,
    Depends,
)
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.devices import (
    DeviceDataUpdateResponse,
    DeviceInfoUpdate,
    DeviceStatusUpdate,
    UpdateDeviceRequest,
    UpdateDeviceResponse,
)
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from sqlalchemy.orm import Session

from . import LoggerRouteHandler


class DeviceStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class DeviceType(Enum):
    QPU = "QPU"
    SIMULATOR = "simulator"


router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.patch(
    "/devices/{device_id}",
    response_model=UpdateDeviceResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_device(
    device_id: str, request: UpdateDeviceRequest, db: Session = Depends(get_db)
) -> UpdateDeviceResponse | ErrorResponse:
    """
    Update a part of properties of the specified device.

    Args:
        device_id (Device): The deviceId.
        request (UpdateDeviceRequest): The request containing the changes to the device.
        db (Session): The database session.

    Returns:
        UpdateDeviceResponse: The response containing the update message.
    """
    logger.info("invoked update_device")
    try:
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        if request.n_qubits is not None:
            device.n_qubits = request.n_qubits

        db.commit()
        return UpdateDeviceResponse()
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.patch(
    "/devices/{device_id}/status",
    response_model=DeviceDataUpdateResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_device_status(
    device_id: str,
    request: DeviceStatusUpdate,
    db: Session = Depends(get_db),
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update the status of a device.

    Args:
        device (Device): The device to update.
        request (DeviceStatusUpdate): The request containing the new status.
        db (Session): The database session.

    Returns:
        DeviceDataUpdateResponse: The response containing the update message.
    """
    logger.info("invoked update_device")
    try:
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        status = request.status
        device.status = status  # type: ignore
        db.commit()
        return DeviceDataUpdateResponse(message="Device's data updated")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.patch(
    "/devices/{device_id}/device_info",
    response_model=DeviceDataUpdateResponse,
    responses={
        400: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_device_calibration(
    device_id: str,
    request: DeviceInfoUpdate,
    db: Session = Depends(get_db),
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update the calibration data and calibrated timestamp for a device.

    Args:
        device (Device): The device to update.
        request (DeviceInfoUpdate): The request object containing the calibration data and calibrated timestamp.
        db (Session): The database session.

    Returns:
        DeviceDataUpdateResponse: The response object indicating the success of the update.

    Raises:
        BadRequest: If the device is not a QPU device, or if the calibration data or calibrated timestamp is missing.
    """
    logger.info("invoked update_device")
    try:
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        device_info = request.device_info
        calibrated_at = request.calibrated_at
        logger.info(f"{calibrated_at}")
        if device.device_type != DeviceType.QPU.value:
            return BadRequestResponse("Calibration is only supported for QPU devices")
        if device_info is None:
            return BadRequestResponse(message="device_info is required")
        if calibrated_at is None:
            return BadRequestResponse(message="calibrated_at is required")
        # device.calibration_data = calibration_data.model_dump_json()
        device.device_info = device_info
        device.calibrated_at = calibrated_at
        db.commit()
        return DeviceDataUpdateResponse(message="Device's data updated")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")
