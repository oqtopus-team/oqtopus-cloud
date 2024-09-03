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
    DeviceDataUpdate,
    DeviceDataUpdateResponse,
    DevicePendingTasksUpdate,
    DeviceStatusUpdate,
)
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from sqlalchemy.orm import Session

from . import LoggerRouteHandler


class DeviceStatus(Enum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class DeviceType(Enum):
    QPU = "QPU"
    SIMULATOR = "simulator"


router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def update_device_status(
    device: Device, request: DeviceStatusUpdate, db: Session
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
    status = request.status
    restart_at = request.restartAt
    if status == DeviceStatus.NOT_AVAILABLE.value:
        if not restart_at:
            return BadRequestResponse("restartAt is required for status NOT_AVAILABLE")
        device.status = status  # type: ignore
        device.restart_at = restart_at
    else:
        if restart_at:
            return BadRequestResponse("restartAt is not required for status AVAILABLE")
        device.status = status  # type: ignore
        device.restart_at = None  # type: ignore
    db.commit()
    return DeviceDataUpdateResponse(message="Device's data updated")


def update_device_pending_tasks(
    device: Device, request: DevicePendingTasksUpdate, db: Session
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update the number of pending tasks for a device.

    Args:
        device (Device): The device to update.
        request (DevicePendingTasksUpdate): The request object containing the new number of pending tasks.
        db (Session): The database session.

    Returns:
        DeviceDataUpdateResponse: The response object indicating the success of the update.

    Raises:
        BadRequest: If the new number of pending tasks is not provided or is less than 0.
    """
    n_pending_tasks = request.nPendingTasks
    if n_pending_tasks is None:
        return BadRequestResponse("nPendingTasks is required")
    if n_pending_tasks < 0:
        return BadRequestResponse("nPendingTasks must be greater than or equal to 0")
    device.pending_tasks = n_pending_tasks
    db.commit()
    return DeviceDataUpdateResponse(message="Device's data updated")


def update_device_calibration(
    device: Device, request: DeviceCalibrationUpdate, db: Session
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
    calibration_data = request.calibrationData
    calibrated_at = request.calibratedAt
    if device.device_type != DeviceType.QPU.value:
        return BadRequestResponse("Calibration is only supported for QPU devices")
    if calibration_data is None:
        return BadRequestResponse(detail="calibrationData is required")
    if calibrated_at is None:
        return BadRequestResponse(detail="calibratedAt is required")
    device.calibration_data = calibration_data.model_dump_json()
    device.calibrated_at = calibrated_at
    db.commit()
    return DeviceDataUpdateResponse(message="Device's data updated")


@router.patch(
    "/internal/devices/{deviceId}",
    response_model=DeviceDataUpdateResponse,
    responses={
        400: {"model": Detail},
        404: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def update_device(
    deviceId: str, request: DeviceDataUpdate, db: Session = Depends(get_db)
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update device information based on the given device ID and request data.

    Args:
        deviceId (str): The ID of the device to be updated.
        request (DeviceDataUpdate): The request data containing the updated device information.
        db (Session, optional): The database session. Defaults to Depends(get_db).

    Returns:
        DeviceDataUpdateResponse: The response containing the updated device information.

    Raises:
        NotFoundError: If the device with the given ID is not found.
        BadRequest: If the request is invalid.
        InternalServerError: If an unexpected error occurs during the update process.
    """
    logger.info("invoked update_device")
    try:
        device = db.get(Device, deviceId)
        if device is None:
            return NotFoundErrorResponse(f"deviceId={deviceId} is not found.")
        if isinstance(request.root, DeviceStatusUpdate):
            return update_device_status(device, request.root, db)
        elif isinstance(request.root, DevicePendingTasksUpdate):
            return update_device_pending_tasks(
                device,
                request.root,
                db,
            )
        elif isinstance(request.root, DeviceCalibrationUpdate):
            return update_device_calibration(
                device,
                request.root,
                db,
            )
        else:
            return BadRequestResponse("Invalid request")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")
