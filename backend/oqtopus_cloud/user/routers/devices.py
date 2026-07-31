import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import Request as Event
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import (
    get_device_info_history_key,
    get_device_info_key,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.devices import (
    DeviceInfo,
    DeviceInfoHistoryDetail,
    DeviceInfoHistoryEntry,
    DeviceInfoHistoryListResponse,
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

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _history_to_entry(history: DeviceInfoHistory) -> DeviceInfoHistoryEntry:
    return DeviceInfoHistoryEntry(
        history_uid=history.history_uid,
        device_id=history.device_id,
        calibrated_at=history.calibrated_at,
        n_qubits=history.n_qubits,
        n_couplings=history.n_couplings,
    )


def _get_history_object_key(history: DeviceInfoHistory) -> str:
    return get_device_info_history_key(history.device_id, history.calibrated_at)


def _history_to_detail(
    history: DeviceInfoHistory, storage: AbstractStorage
) -> DeviceInfoHistoryDetail:
    return DeviceInfoHistoryDetail(
        history_uid=history.history_uid,
        device_id=history.device_id,
        calibrated_at=history.calibrated_at,
        n_qubits=history.n_qubits,
        n_couplings=history.n_couplings,
        device_info=storage.get_download_presigned_url(
            key=_get_history_object_key(history)
        ),
    )


def _check_user_device_access(
    device_id: str, event: Event, db: Session
) -> Device | ErrorResponse:
    user_id = event.state.user_id
    available_devices = get_user_available_devices(user_id, db)

    if available_devices != "*" and device_id not in available_devices:
        logger.error(f"{user_id} is not allowed to access device_id={device_id}.")
        return ForbiddenErrorResponse(message=f"Cannot access device_id={device_id}.")

    device = db.scalars(select(Device).where(Device.id == device_id)).first()
    if device is None:
        message = f"device_id={device_id} is not found."
        logger.info(message)
        return NotFoundErrorResponse(message=message)
    return device


def _apply_history_filters(
    stmt,
    count_stmt,
    from_: datetime | None,
    to: datetime | None,
):
    if from_ is not None:
        from_ = _normalize_utc(from_)
        stmt = stmt.where(DeviceInfoHistory.calibrated_at >= from_)
        count_stmt = count_stmt.where(DeviceInfoHistory.calibrated_at >= from_)
    if to is not None:
        to = _normalize_utc(to)
        stmt = stmt.where(DeviceInfoHistory.calibrated_at <= to)
        count_stmt = count_stmt.where(DeviceInfoHistory.calibrated_at <= to)
    return stmt, count_stmt


@router.get(
    "/devices", response_model=list[DeviceInfo], responses={500: {"model": Message}}
)
@tracer.capture_method
def get_devices(
    event: Event,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> list[DeviceInfo] | ErrorResponse:
    try:
        logger.info("invoked list_devices")
        available_devices = get_user_available_devices(event.state.user_id, db)

        if available_devices == "*":
            devices = db.scalars(select(Device)).all()
        else:
            devices = db.scalars(
                select(Device).where(Device.id.in_(available_devices))
            ).all()

        return [model_to_schema(device, storage) for device in devices]
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
    storage: AbstractStorage = Depends(get_storage),
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
        user_id = event.state.user_id
        logger.info(f"User {user_id} is trying to access device_id={device_id}.")
        available_devices = get_user_available_devices(user_id, db)

        if available_devices != "*" and device_id not in available_devices:
            logger.error(f"{user_id} is not allowed to access device_id={device_id}.")
            return ForbiddenErrorResponse(
                message=f"Cannot access device_id={device_id}."
            )

        device = db.scalars(select(Device).where(Device.id == device_id)).first()
        logger.info("invoked get_device")
        if device:
            response = model_to_schema(device, storage)
            return response
        else:
            message = f"device_id={device_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/device_histories",
    response_model=DeviceInfoHistoryListResponse,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def list_device_histories(
    event: Event,
    device_id: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> DeviceInfoHistoryListResponse | ErrorResponse:
    try:
        stmt = select(DeviceInfoHistory)
        count_stmt = select(func.count()).select_from(DeviceInfoHistory)

        if device_id is not None:
            access_result = _check_user_device_access(device_id, event, db)
            if isinstance(access_result, ErrorResponse):
                return access_result
            stmt = stmt.where(DeviceInfoHistory.device_id == device_id)
            count_stmt = count_stmt.where(DeviceInfoHistory.device_id == device_id)
        else:
            available_devices = get_user_available_devices(event.state.user_id, db)
            if available_devices != "*":
                if len(available_devices) == 0:
                    return DeviceInfoHistoryListResponse(
                        items=[], total=0, limit=limit, offset=offset
                    )
                stmt = stmt.where(DeviceInfoHistory.device_id.in_(available_devices))
                count_stmt = count_stmt.where(
                    DeviceInfoHistory.device_id.in_(available_devices)
                )

        stmt, count_stmt = _apply_history_filters(stmt, count_stmt, from_, to)
        total = db.scalar(count_stmt) or 0
        histories = db.scalars(
            stmt.order_by(DeviceInfoHistory.calibrated_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return DeviceInfoHistoryListResponse(
            items=[_history_to_entry(history) for history in histories],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/device_histories/{history_uid}",
    response_model=DeviceInfoHistoryDetail,
    responses={
        403: {"model": Message},
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_device_history(
    history_uid: str,
    event: Event,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> DeviceInfoHistoryDetail | ErrorResponse:
    try:
        history = db.scalars(
            select(DeviceInfoHistory).where(
                DeviceInfoHistory.history_uid == history_uid
            )
        ).first()
        if history is None:
            return NotFoundErrorResponse(
                message=f"device_info_history history_uid={history_uid} is not found."
            )

        access_result = _check_user_device_access(history.device_id, event, db)
        if isinstance(access_result, ErrorResponse):
            return access_result

        if not storage.does_exist(key=_get_history_object_key(history)):
            return NotFoundErrorResponse(message="device_info object is not found.")
        return _history_to_detail(history, storage)
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
    "calibrated_at": "calibrated_at",
    "description": "description",
}


def get_device_info(
    model: Device, storage: AbstractStorage | None = None
) -> str | None:
    if storage is None or not hasattr(storage, "does_exist"):
        return getattr(model, "device_info", None)
    device_info_key = get_device_info_key(model.id)
    if storage.does_exist(key=device_info_key):
        return storage.get_download_presigned_url(key=device_info_key)
    return getattr(model, "device_info", None)


def model_to_schema(
    model: Device, storage: AbstractStorage | None = None
) -> DeviceInfo:
    dict = {
        "device_id": getattr(model, "id", None),
        "device_type": getattr(model, "device_type", None),
        "status": model.status,
        "available_at": getattr(model, "available_at", None),
        "n_pending_jobs": getattr(model, "pending_jobs", None),
        "n_qubits": getattr(model, "n_qubits", None),
        "basis_gates": json.loads(getattr(model, "basis_gates", "[]")),
        "supported_instructions": json.loads(getattr(model, "instructions", "[]")),
        "device_info": get_device_info(model, storage),
        "calibrated_at": getattr(model, "calibrated_at", None),
        "description": model.description,
    }
    return DeviceInfo.model_validate(dict)


def get_user_available_devices(user_id: str, db: Session) -> list[str] | str:
    try:
        user = db.scalars(select(User).where(User.id == user_id)).first()
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
