import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.devices import (
    DeviceBase,
    DeviceInfo,
    DeviceInfoHistoryDetail,
    DeviceInfoHistoryEntry,
    DeviceInfoHistoryListResponse,
    DeviceInfoUploadPresignedURL,
    DeviceInfoUploadResponse,
    DevicePatch,
)
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    ErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.admin.schemas.success import SuccessResponse
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.storages import AbstractStorage, get_storage
from oqtopus_cloud.common.storages.storage_utils import (
    get_device_info_history_key,
    get_device_info_key,
)

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)
utc = ZoneInfo("UTC")


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _history_to_entry(history: DeviceInfoHistory) -> DeviceInfoHistoryEntry:
    return DeviceInfoHistoryEntry(
        history_id=history.history_id,
        device_id=history.device_id,
        calibrated_at=history.calibrated_at,
        n_qubits=history.n_qubits,
        n_couplings=history.n_couplings,
    )


def _get_history_object_key(history: DeviceInfoHistory) -> str:
    return get_device_info_history_key(history.history_id)


def _history_to_detail(
    history: DeviceInfoHistory, storage: AbstractStorage
) -> DeviceInfoHistoryDetail:
    return DeviceInfoHistoryDetail(
        history_id=history.history_id,
        device_id=history.device_id,
        calibrated_at=history.calibrated_at,
        n_qubits=history.n_qubits,
        n_couplings=history.n_couplings,
        device_info=storage.get_download_presigned_url(
            key=_get_history_object_key(history)
        ),
    )


def _get_existing_device(device_id: str, db: Session) -> Device | ErrorResponse:
    device = db.scalars(select(Device).where(Device.id == device_id)).first()
    if device is None:
        return NotFoundErrorResponse(message=f"device_id={device_id} is not found.")
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
    "/devices",
    response_model=list[DeviceInfo],
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_devices(
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> list[DeviceInfo] | ErrorResponse:
    try:
        logger.info("invoked get_devices")
        devices = db.scalars(select(Device)).all()
        return [model_to_schema(device, storage) for device in devices]
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.get(
    "/devices/{device_id}",
    response_model=DeviceInfo,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> DeviceInfo | ErrorResponse:
    try:
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
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def list_device_histories(
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
            device = _get_existing_device(device_id, db)
            if isinstance(device, ErrorResponse):
                return device
            stmt = stmt.where(DeviceInfoHistory.device_id == device_id)
            count_stmt = count_stmt.where(DeviceInfoHistory.device_id == device_id)

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
    "/device_histories/{history_id}",
    response_model=DeviceInfoHistoryDetail,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def get_device_history(
    history_id: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> DeviceInfoHistoryDetail | ErrorResponse:
    try:
        history = db.scalars(
            select(DeviceInfoHistory).where(DeviceInfoHistory.history_id == history_id)
        ).first()
        if history is None:
            return NotFoundErrorResponse(
                message=f"device_info_history history_id={history_id} is not found."
            )

        if not storage.does_exist(key=_get_history_object_key(history)):
            return NotFoundErrorResponse(message="device_info object is not found.")
        return _history_to_detail(history, storage)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/device_histories/{history_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_device_history(
    history_id: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked delete device history")
        history = db.scalars(
            select(DeviceInfoHistory).where(DeviceInfoHistory.history_id == history_id)
        ).first()
        if history is None:
            return NotFoundErrorResponse(
                message=f"device_info_history history_id={history_id} is not found."
            )

        history_key = _get_history_object_key(history)
        if storage.does_exist(key=history_key):
            storage.delete(key=history_key)
        else:
            logger.warning("device_info_history object is not found: %s", history_key)
        db.delete(history)
        db.commit()
        return SuccessResponse(message="Device history deleted successfully")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


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
    try:
        device = db.scalars(select(Device).where(Device.id == device_id)).first()
        if device is None:
            return NotFoundErrorResponse(message=f"device_id={device_id} is not found.")
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


@router.post(
    "/devices",
    response_model=SuccessResponse,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def register_devices(
    device_info: DeviceBase = Body(..., description="device information"),
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked register_devices")
        device_id = get_device_id(device_info)
        if device_id is None:
            logger.error("device_id is required")
            return BadRequestErrorResponse(message="device_id is required")
        existing_device = db.scalars(
            select(Device).where(Device.id == device_id)
        ).first()
        if existing_device:
            logger.error(f"device_id={device_id} already exists")
            return BadRequestErrorResponse(
                message=f"device_id={device_id} already exists"
            )
        new_device = schema_to_model(device_id, device_info)
        if new_device is None:
            logger.error("Invalid device timezone")
            return BadRequestErrorResponse(message="Invalid device timezone")
        db.add(new_device)
        db.commit()
        return SuccessResponse(message="Device registered successfully")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.patch(
    "/devices/{device_id}",
    response_model=SuccessResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_device_data(
    device_id: str,
    device_update: DevicePatch = Body(..., description="new status"),
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked update device data")
        # query
        stmt = select(Device).where(Device.id == device_id)
        query = db.execute(stmt).scalars().first()
        if not query:
            logger.error(f"device_id={device_id} is not found")
            return NotFoundErrorResponse(message=f"device_id={device_id} is not found.")
        update_fields = device_update.model_dump(exclude_none=True)
        for field, value in update_fields.items():
            if field == "basis_gates" and isinstance(value, list):
                value = json.dumps(value)
            if field == "supported_instructions" and isinstance(value, list):
                value = json.dumps(value)
                field = "instructions"
            setattr(query, field, value)
        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        return SuccessResponse(message="Device updated successfully")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/devices/{device_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    storage: AbstractStorage = Depends(get_storage),
) -> SuccessResponse | ErrorResponse:
    try:
        logger.info("invoked delete device")
        # query
        stmt = select(Device).where(Device.id == device_id)
        # pageination
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            logger.error(f"device_id={device_id} is not found")
            return NotFoundErrorResponse(message="Device not found")
        device_info_key = get_device_info_key(device_id)
        if storage.does_exist(key=device_info_key):
            storage.delete(key=device_info_key)
        histories = db.scalars(
            select(DeviceInfoHistory).where(DeviceInfoHistory.device_id == device_id)
        ).all()
        for history in histories:
            history_key = _get_history_object_key(history)
            if storage.does_exist(key=history_key):
                storage.delete(key=history_key)
            db.delete(history)
        # delete from RDS
        db.delete(query_result)
        db.commit()
        return SuccessResponse(message="Device deleted successfully")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def get_device_id(device_base: DeviceBase) -> str | None:
    try:
        if device_base.device_info is None:
            return None
        device_info = json.loads(device_base.device_info)
        return device_info.get("device_id", None)
    except Exception:
        return None


def ensure_timezone(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=utc)
    if dt.utcoffset() != timedelta(0):
        raise ValueError("Datetime is not in UTC.")
    return dt


def get_device_info(model: Device, storage: AbstractStorage) -> str | None:
    device_info_key = get_device_info_key(model.id)
    if storage.does_exist(key=device_info_key):
        return storage.get_download_presigned_url(key=device_info_key)
    return getattr(model, "device_info", None)


def model_to_schema(model: Device, storage: AbstractStorage) -> DeviceInfo:
    dict = {
        "device_id": getattr(model, "id", None),
        "device_type": getattr(model, "device_type", None),
        "status": model.status,
        "available_at": ensure_timezone(getattr(model, "available_at", None)),
        "n_pending_jobs": getattr(model, "pending_jobs", None),
        "n_qubits": getattr(model, "n_qubits", None),
        "basis_gates": json.loads(getattr(model, "basis_gates", "[]")),
        "supported_instructions": json.loads(getattr(model, "instructions", "[]")),
        "device_info": get_device_info(model, storage),
        "calibrated_at": ensure_timezone(getattr(model, "calibrated_at", None)),
        "description": model.description,
    }
    return DeviceInfo.model_validate(dict)


def schema_to_model(device_id: str, schema: DeviceBase) -> Device | None:
    try:
        model = Device(
            id=device_id,
            device_type=schema.device_type,
            status=schema.status,
            available_at=ensure_timezone(schema.available_at),
            n_qubits=schema.n_qubits,
            basis_gates=json.dumps(schema.basis_gates),
            instructions=json.dumps(schema.supported_instructions),
            device_info=schema.device_info,
            calibrated_at=ensure_timezone(schema.calibrated_at),
            description=schema.description,
        )
        return model
    except Exception:
        return None
