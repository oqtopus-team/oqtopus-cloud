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
    DevicePendingJobsUpdate,
    DeviceDataUpdate,
    DeviceDataUpdateResponse,
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
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


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
    available_at = request.available_at
    if status == DeviceStatus.UNAVAILABLE.value:
        if not available_at:
            return BadRequestResponse("available_at is required for status unavailable")
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


def update_device_pending_jobs(
    device: Device, request: DevicePendingJobsUpdate, db: Session
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update the number of pending jobs for a device.

    Args:
        device (Device): The device to update.
        request (DevicePendingJobsUpdate): The request object containing the new number of pending jobs.
        db (Session): The database session.

    Returns:
        DeviceDataUpdateResponse: The response object indicating the success of the update.

    Raises:
        BadRequest: If the new number of pending jobs is not provided or is less than 0.
    """
    n_pending_jobs = request.n_pending_jobs
    if n_pending_jobs is None:
        return BadRequestResponse("n_pending_jobs is required")
    if n_pending_jobs < 0:
        return BadRequestResponse("n_pending_jobs must be greater than or equal to 0")
    device.pending_jobs = n_pending_jobs
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
    device_info = request.device_info
    calibrated_at = request.calibrated_at
    if device.device_type != DeviceType.QPU.value:
        return BadRequestResponse("Calibration is only supported for QPU devices")
    if device_info is None:
        return BadRequestResponse(detail="device_info is required")
    if calibrated_at is None:
        return BadRequestResponse(detail="calibrated_at is required")
    # device.calibration_data = calibration_data.model_dump_json()
    device.device_info = device_info
    device.calibrated_at = calibrated_at
    db.commit()
    return DeviceDataUpdateResponse(message="Device's data updated")


@router.patch(
    "/devices/{device_id}",
    response_model=DeviceDataUpdateResponse,
    responses={
        400: {"model": Detail},
        404: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def update_device(
    device_id: str, request: DeviceDataUpdate, db: Session = Depends(get_db)
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Update device information based on the given device ID and request data.

    Args:
        device_id (str): The ID of the device to be updated.
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
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        if isinstance(request.root, DeviceStatusUpdate):
            return update_device_status(device, request.root, db)
        elif isinstance(request.root, DevicePendingJobsUpdate):
            return update_device_pending_jobs(
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
