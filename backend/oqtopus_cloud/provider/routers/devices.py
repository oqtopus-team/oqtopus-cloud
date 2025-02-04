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
    DeviceCalibrationUpdate,
    DeviceDataUpdateResponse,
    DeviceStatusUpdate,
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
    device_id: Device, request: DeviceStatusUpdate, db: Session = Depends(get_db)
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
        available_at = request.available_at
        if status == DeviceStatus.UNAVAILABLE.value:
            if not available_at:
                return BadRequestResponse(
                    "available_at is required for status unavailable"
                )
            device.status = status  # type: ignore
            device.available_at = available_at
        else:
            if available_at:
                return BadRequestResponse(
                    "available_at is not required for status available"
                )
            device.status = status  # type: ignore
            device.available_at = None  # type: ignore
        db.commit()
        return DeviceDataUpdateResponse(message="Device's data updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


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
    device_id: Device, request: DeviceCalibrationUpdate, db: Session = Depends(get_db)
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update the calibration data and calibrated timestamp for a device.

    Args:
        device (Device): The device to update.
        request (DeviceCalibrationUpdate): The request object containing the calibration data and calibrated timestamp.
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
        return InternalServerErrorResponse(f"Error: {str(e)}")
