from enum import Enum

from fastapi import (
    APIRouter,
    Depends,
)
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import get_device_info_key
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.devices import (
    DeviceDataUpdateResponse,
    DeviceInfoUpdate,
    DeviceInfoUploadPresignedURL,
    DeviceInfoUploadResponse,
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


@router.get(
    "/devices/{device_id}/device_info/upload",
    response_model=DeviceInfoUploadResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_device_info_upload_url(
    device_id: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> DeviceInfoUploadResponse | ErrorResponse:
    logger.info("invoked get_device_info_upload_url")
    try:
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        return DeviceInfoUploadResponse(
            presigned_url=DeviceInfoUploadPresignedURL(
                **storage.get_upload_presigned_url_data(
                    key=get_device_info_key(device_id)
                )
            )
        )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


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
    storage: AbstractStorage = Depends(get_storage),
) -> DeviceDataUpdateResponse | ErrorResponse:
    """
    Confirm uploaded device_info and update the calibrated timestamp for a device.

    Args:
        device (Device): The device to update.
        request (DeviceInfoUpdate): The request object containing the calibrated timestamp.
        db (Session): The database session.

    Returns:
        DeviceDataUpdateResponse: The response object indicating the success of the update.

    Raises:
        BadRequest: If the uploaded device_info or calibrated timestamp is missing.
    """
    logger.info("invoked update_device")
    try:
        device = db.get(Device, device_id)
        if device is None:
            return NotFoundErrorResponse(f"device_id={device_id} is not found.")
        calibrated_at = request.calibrated_at
        logger.info(f"{calibrated_at}")
        if calibrated_at is None:
            return BadRequestResponse(message="calibrated_at is required")

        device_info_key = get_device_info_key(device_id)
        if not storage.does_exist(key=device_info_key):
            return BadRequestResponse(message="device_info upload not found")
        device.device_info = device_info_key
        device.calibrated_at = calibrated_at
        db.commit()
        return DeviceDataUpdateResponse(message="Device's data updated")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")
