import datetime
import json
import zipfile
from enum import Enum
from io import BytesIO
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
)
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import (
    get_device_info_history_key,
    get_device_info_key,
    get_device_info_upload_key,
)
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
    ConflictErrorResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from sqlalchemy.orm import Session
from uuid_extensions import uuid7

from . import LoggerRouteHandler


class DeviceStatus(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class DeviceType(Enum):
    QPU = "QPU"
    SIMULATOR = "simulator"


router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def _normalize_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def _count_device_info_metadata(device_info: dict) -> tuple[int, int]:
    qubits = device_info.get("qubits", [])
    couplings = device_info.get("couplings", [])
    return len(qubits), len(couplings)


def _extract_device_info_metadata(device_info_data: bytes) -> tuple[int, int]:
    try:
        with zipfile.ZipFile(BytesIO(device_info_data)) as archive:
            file_names = [name for name in archive.namelist() if not name.endswith("/")]
            if not file_names:
                raise ValueError("device_info.zip does not contain a device info file")
            with archive.open(file_names[0]) as device_info_file:
                device_info = json.load(device_info_file)
        return _count_device_info_metadata(device_info)
    except zipfile.BadZipFile:
        pass
    except (json.JSONDecodeError, KeyError) as exc:
        raise ValueError("device_info.zip is invalid") from exc

    try:
        device_info = json.loads(device_info_data.decode())
        return _count_device_info_metadata(device_info)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("device_info is invalid") from exc


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
        upload_id = uuid4().hex
        return DeviceInfoUploadResponse(
            upload_id=upload_id,
            presigned_url=DeviceInfoUploadPresignedURL(
                **storage.get_upload_presigned_url_data(
                    key=get_device_info_upload_key(device_id, upload_id)
                )
            ),
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
        409: {"model": Message},
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
        calibrated_at = _normalize_utc(calibrated_at)

        existing_history = (
            db.query(DeviceInfoHistory)
            .filter(
                DeviceInfoHistory.device_id == device_id,
                DeviceInfoHistory.calibrated_at == calibrated_at,
            )
            .first()
        )
        if existing_history is not None:
            return ConflictErrorResponse(
                message=(
                    f"device_info_history for device_id={device_id} and "
                    f"calibrated_at={calibrated_at.isoformat()} already exists."
                )
            )

        upload_key = get_device_info_upload_key(device_id, request.upload_id)
        uploaded_device_info = storage.get(key=upload_key)
        if uploaded_device_info is None:
            return BadRequestResponse(message="device_info upload not found")
        n_qubits, n_couplings = _extract_device_info_metadata(uploaded_device_info)

        device_info_key = get_device_info_key(device_id)
        history_id = str(uuid7())
        history_key = get_device_info_history_key(history_id)
        storage.put(key=history_key, data=uploaded_device_info)
        storage.put(key=device_info_key, data=uploaded_device_info)
        storage.delete(key=upload_key)
        device.calibrated_at = calibrated_at
        db.add(
            DeviceInfoHistory(
                history_id=history_id,
                device_id=device_id,
                calibrated_at=calibrated_at,
                n_qubits=n_qubits,
                n_couplings=n_couplings,
            )
        )
        db.commit()
        return DeviceDataUpdateResponse(message="Device's data updated")
    except ValueError as e:
        return BadRequestResponse(message=str(e))
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")
