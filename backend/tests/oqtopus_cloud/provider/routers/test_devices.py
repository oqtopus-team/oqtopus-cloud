import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pytest
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.storages.storage_utils import (
    get_device_info_history_key,
    get_device_info_key,
    get_device_info_upload_key,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.routers.devices import (
    get_device_info_upload_url,
    update_device,
    update_device_calibration,
    update_device_status,
)
from oqtopus_cloud.provider.schemas.devices import (
    DeviceDataUpdateResponse,
    DeviceInfoUpdate,
    DeviceInfoUploadResponse,
    DeviceStatusUpdate,
    UpdateDeviceRequest,
    UpdateDeviceResponse,
)
from oqtopus_cloud.provider.schemas.devices import Status as DeviceStatus
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    ConflictErrorResponse,
    InternalServerErrorResponse,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

utc = ZoneInfo("UTC")
client = TestClient(app)


def _get_calibration_dict() -> Dict:
    calib_dict = {
        "qubitConnectivity": ["(1,4)", "(4,5)", "(5,8)"],
        "t1": {"0": 55.51, "1": 37.03, "2": 57.13},
        "t2": {"0": 99.31, "1": 111.03, "2": 30.12},
        "roError": {"0": 4.67e-2, "1": 1.8e-1, "2": 3.55e-1},
        "gateError": {"sx": {"0": 6.92e-3, "1": 2.96e-3, "2": 7.2e-2}},
        "measProb0As1": {"0": 6.08e-3, "1": 1.2e-2, "2": 2.48e-1},
        "measProb1As0": {"0": 2.81e-2, "1": 3.86e-1, "2": 8.11e-2},
        "gateDuration": {"sx": {"0": 29.3, "1": 50.9, "2": 45.4}},
    }
    return calib_dict


def _get_device_info_dict() -> Dict:
    return {
        "device_id": "SC",
        "qubits": [{"id": 0}, {"id": 1}],
        "couplings": [{"control": 0, "target": 1}],
    }


def _stage_device_info(test_storage, device_id: str, data: bytes) -> str:
    upload_id = str(uuid4())
    test_storage.put(
        key=get_device_info_upload_key(device_id, upload_id), data=data
    )
    return upload_id


def _get_model_sim():
    mode_dict = {
        "id": "SC2",
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56).replace(tzinfo=timezone.utc),
        "pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Device(**mode_dict)


def _get_model_qpu():
    mode_dict = {
        "id": "SC",
        "device_type": "QPU",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Device(**mode_dict)


def test_update_device_n_qubits(test_db):
    test_db.add(_get_model_sim())
    test_db.commit()

    device_bef = test_db.get(Device, "SC2")
    n_qubits_bef = device_bef.n_qubits
    request = UpdateDeviceRequest(n_qubits=device_bef.n_qubits + 10)
    resp = update_device(device_id="SC2", request=request, db=test_db)
    assert isinstance(resp, UpdateDeviceResponse)
    device_aft = test_db.get(Device, "SC2")
    assert device_aft.n_qubits == n_qubits_bef + 10
    # Properties other than n_qubits should remain same.
    assert device_aft.description == device_bef.description
    assert device_aft.device_type == device_bef.device_type
    assert device_aft.status == device_bef.status
    assert device_aft.calibrated_at == device_bef.calibrated_at
    assert device_aft.available_at == device_bef.available_at
    assert device_aft.basis_gates == device_bef.basis_gates
    assert device_aft.instructions == device_bef.instructions
    assert device_aft.pending_jobs == device_bef.pending_jobs


def test_update_device_status_available(test_db):
    # Arrange
    test_db.add(_get_model_sim())
    test_db.commit()
    device = test_db.get(Device, "SC2")
    # Act
    request = DeviceStatusUpdate(status=DeviceStatus.available)
    actual = update_device_status(device_id=device.id, request=request, db=test_db)
    # Assert
    expected = DeviceDataUpdateResponse(message="Device's data updated")
    assert actual == expected


def test_update_device_status_not_available(test_db):
    # Arrange
    test_db.add(_get_model_sim())
    test_db.commit()
    device = test_db.get(Device, "SC2")
    # Act
    request = DeviceStatusUpdate(status=DeviceStatus.unavailable)
    actual = update_device_status(device_id=device.id, request=request, db=test_db)
    # Assert
    expected = DeviceDataUpdateResponse(message="Device's data updated")
    assert actual == expected


def test_update_device_calibration_qpu(test_db, test_storage):
    # Arrange
    test_db.add(_get_model_qpu())
    test_db.commit()
    device = test_db.get(Device, "SC")
    device_info_key = get_device_info_key(device.id)
    upload_id = _stage_device_info(
        test_storage, device.id, json.dumps(_get_calibration_dict()).encode()
    )
    # Act
    request = DeviceInfoUpdate(
        upload_id=upload_id,
        calibrated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
    )
    actual = update_device_calibration(
        device_id=device.id, request=request, db=test_db, storage=test_storage
    )
    # Assert
    expected = DeviceDataUpdateResponse(message="Device's data updated")
    assert actual == expected
    assert test_storage.does_exist(key=device_info_key)
    assert test_db.get(Device, "SC").calibrated_at == request.calibrated_at


def test_update_device_calibration_sim(test_db, test_storage):
    # Arrange
    test_db.add(_get_model_sim())
    test_db.commit()
    device = test_db.get(Device, "SC2")
    device_info_key = get_device_info_key(device.id)
    upload_id = _stage_device_info(
        test_storage, device.id, json.dumps(_get_calibration_dict()).encode()
    )
    # Act
    request = DeviceInfoUpdate(
        upload_id=upload_id,
        calibrated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
    )
    actual = update_device_calibration(
        device_id=device.id, request=request, db=test_db, storage=test_storage
    )
    # Assert
    expected = DeviceDataUpdateResponse(message="Device's data updated")
    assert actual == expected
    assert test_storage.does_exist(key=device_info_key)
    assert test_db.get(Device, "SC2").calibrated_at == request.calibrated_at


def test_get_device_info_upload_url(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()

    first = get_device_info_upload_url("SC", test_db, test_storage)
    second = get_device_info_upload_url("SC", test_db, test_storage)

    assert isinstance(first, DeviceInfoUploadResponse)
    assert isinstance(second, DeviceInfoUploadResponse)
    assert first.upload_id != second.upload_id
    assert str(first.upload_id) in first.presigned_url.url
    assert str(first.upload_id) in first.presigned_url.fields["key"]


def test_update_device_calibration_with_uploaded_device_info(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    device_info_key = get_device_info_key("SC")
    upload_id = _stage_device_info(
        test_storage, "SC", json.dumps(_get_calibration_dict()).encode()
    )

    request = DeviceInfoUpdate(
        upload_id=upload_id,
        calibrated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
    )
    actual = update_device_calibration("SC", request, test_db, test_storage)

    assert actual == DeviceDataUpdateResponse(message="Device's data updated")
    assert test_storage.does_exist(key=device_info_key)
    assert test_db.get(Device, "SC").calibrated_at == request.calibrated_at


def test_update_device_calibration_creates_history(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    calibrated_at = datetime(2025, 4, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    device_info = json.dumps(_get_device_info_dict()).encode()
    upload_id = _stage_device_info(test_storage, "SC", device_info)

    actual = update_device_calibration(
        "SC",
        DeviceInfoUpdate(upload_id=upload_id, calibrated_at=calibrated_at),
        test_db,
        test_storage,
    )

    history = test_db.query(DeviceInfoHistory).filter_by(device_id="SC").one()
    assert actual == DeviceDataUpdateResponse(message="Device's data updated")
    assert history.n_qubits == 2
    assert history.n_couplings == 1
    assert (
        test_storage.get(key=get_device_info_history_key(history.history_id))
        == device_info
    )
    assert not test_storage.does_exist(
        key=get_device_info_upload_key("SC", upload_id)
    )


def test_update_device_calibration_binds_interleaved_uploads(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    first_device_info = json.dumps(
        {"device_id": "SC", "qubits": [{"id": 0}], "couplings": []}
    ).encode()
    second_device_info = json.dumps(_get_device_info_dict()).encode()
    first_upload_id = _stage_device_info(test_storage, "SC", first_device_info)
    second_upload_id = _stage_device_info(test_storage, "SC", second_device_info)

    first_result = update_device_calibration(
        "SC",
        DeviceInfoUpdate(
            upload_id=first_upload_id,
            calibrated_at=datetime(2025, 4, 1, tzinfo=timezone.utc),
        ),
        test_db,
        test_storage,
    )
    second_result = update_device_calibration(
        "SC",
        DeviceInfoUpdate(
            upload_id=second_upload_id,
            calibrated_at=datetime(2025, 4, 2, tzinfo=timezone.utc),
        ),
        test_db,
        test_storage,
    )

    histories = test_db.query(DeviceInfoHistory).order_by(
        DeviceInfoHistory.calibrated_at
    )
    archived_device_info = [
        test_storage.get(key=get_device_info_history_key(history.history_id))
        for history in histories
    ]
    assert first_result == DeviceDataUpdateResponse(message="Device's data updated")
    assert second_result == DeviceDataUpdateResponse(message="Device's data updated")
    assert archived_device_info == [first_device_info, second_device_info]
    assert test_storage.get(key=get_device_info_key("SC")) == second_device_info
    assert not test_storage.does_exist(
        key=get_device_info_upload_key("SC", first_upload_id)
    )
    assert not test_storage.does_exist(
        key=get_device_info_upload_key("SC", second_upload_id)
    )


def test_update_device_calibration_rejects_duplicate_history(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    calibrated_at = datetime(2025, 4, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    device_info = json.dumps(_get_device_info_dict()).encode()

    first_request = DeviceInfoUpdate(
        upload_id=_stage_device_info(test_storage, "SC", device_info),
        calibrated_at=calibrated_at,
    )
    second_upload_id = _stage_device_info(test_storage, "SC", device_info)
    second_request = DeviceInfoUpdate(
        upload_id=second_upload_id, calibrated_at=calibrated_at
    )
    update_device_calibration("SC", first_request, test_db, test_storage)
    actual = update_device_calibration("SC", second_request, test_db, test_storage)

    assert isinstance(actual, ConflictErrorResponse)
    assert actual.status_code == 409
    assert not test_storage.does_exist(
        key=get_device_info_upload_key("SC", second_upload_id)
    )


def test_update_device_calibration_returns_conflict_on_integrity_error(
    test_db, test_storage
):
    test_db.add(_get_model_qpu())
    Session.commit(test_db)
    calibrated_at = datetime(2025, 4, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    upload_id = _stage_device_info(
        test_storage, "SC", json.dumps(_get_device_info_dict()).encode()
    )

    with patch.object(
        test_db,
        "commit",
        side_effect=IntegrityError("insert", {}, RuntimeError("duplicate")),
    ):
        actual = update_device_calibration(
            "SC",
            DeviceInfoUpdate(upload_id=upload_id, calibrated_at=calibrated_at),
            test_db,
            test_storage,
        )

    assert isinstance(actual, ConflictErrorResponse)
    assert actual.status_code == 409
    assert test_db.query(DeviceInfoHistory).count() == 0


def test_update_device_calibration_recovers_after_commit_failure(test_db, test_storage):
    test_db.add(_get_model_qpu())
    Session.commit(test_db)
    calibrated_at = datetime(2025, 4, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    first_device_info = json.dumps(_get_device_info_dict()).encode()
    changed_device_info = json.dumps(
        {"device_id": "SC", "qubits": [{"id": 0}], "couplings": []}
    ).encode()
    device_info_key = get_device_info_key("SC")
    upload_id = _stage_device_info(test_storage, "SC", first_device_info)
    request = DeviceInfoUpdate(upload_id=upload_id, calibrated_at=calibrated_at)
    real_commit = test_db.commit
    commit_attempts = 0

    def fail_once_then_commit():
        nonlocal commit_attempts
        commit_attempts += 1
        if commit_attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    with patch.object(test_db, "commit", side_effect=fail_once_then_commit):
        first_result = update_device_calibration("SC", request, test_db, test_storage)
        assert isinstance(first_result, InternalServerErrorResponse)
        assert test_db.query(DeviceInfoHistory).count() == 0

        test_storage.put(key=device_info_key, data=changed_device_info)
        retry_result = update_device_calibration("SC", request, test_db, test_storage)

    history = test_db.query(DeviceInfoHistory).one()
    assert retry_result == DeviceDataUpdateResponse(message="Device's data updated")
    assert history.n_qubits == 2
    assert history.n_couplings == 1
    assert (
        test_storage.get(key=get_device_info_history_key(history.history_id))
        == first_device_info
    )
    assert test_storage.get(key=device_info_key) == first_device_info


def test_update_device_calibration_requires_device_info(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    current_device_info = json.dumps(_get_device_info_dict()).encode()
    test_storage.put(key=get_device_info_key("SC"), data=current_device_info)

    request = DeviceInfoUpdate(
        upload_id=uuid4(),
        calibrated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
    )
    actual = update_device_calibration("SC", request, test_db, test_storage)

    assert isinstance(actual, BadRequestResponse)
    assert actual.status_code == 400
    assert json.loads(actual.body) == {"message": "device_info is required"}
    assert test_storage.get(key=get_device_info_key("SC")) == current_device_info


def test_update_device_calibration_rejects_invalid_upload_id(test_db):
    response = client.patch(
        "/devices/SC/device_info",
        json={
            "upload_id": "../../devices/SC",
            "calibrated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"[]", "device_info must be a JSON object"),
        (b"null", "device_info must be a JSON object"),
        (
            b'{"qubits": null, "couplings": []}',
            "device_info.qubits must be an array",
        ),
        (
            b'{"qubits": [], "couplings": {}}',
            "device_info.couplings must be an array",
        ),
    ],
)
def test_update_device_calibration_rejects_invalid_json_shape(
    test_db, test_storage, payload, message
):
    test_db.add(_get_model_qpu())
    test_db.commit()
    upload_id = _stage_device_info(test_storage, "SC", payload)

    actual = update_device_calibration(
        "SC",
        DeviceInfoUpdate(
            upload_id=upload_id, calibrated_at=datetime.now(timezone.utc)
        ),
        test_db,
        test_storage,
    )

    assert isinstance(actual, BadRequestResponse)
    assert json.loads(actual.body) == {"message": message}
    assert test_db.query(DeviceInfoHistory).count() == 0
    assert not test_storage.does_exist(
        key=get_device_info_upload_key("SC", upload_id)
    )


def test_update_device_calibration_rejects_multiple_zip_entries(test_db, test_storage):
    test_db.add(_get_model_qpu())
    test_db.commit()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("device_info.json", json.dumps(_get_device_info_dict()))
        archive.writestr("unexpected.json", "{}")
    upload_id = _stage_device_info(test_storage, "SC", buffer.getvalue())

    actual = update_device_calibration(
        "SC",
        DeviceInfoUpdate(
            upload_id=upload_id, calibrated_at=datetime.now(timezone.utc)
        ),
        test_db,
        test_storage,
    )

    assert isinstance(actual, BadRequestResponse)
    assert json.loads(actual.body) == {
        "message": "device_info.zip must contain exactly one file"
    }
    assert test_db.query(DeviceInfoHistory).count() == 0


def test_update_device_info_timezone(test_db, test_storage):
    # Arrange
    test_db.add(_get_model_qpu())
    test_db.commit()
    upload_id = _stage_device_info(
        test_storage, "SC", json.dumps(_get_calibration_dict()).encode()
    )

    req = DeviceInfoUpdate.model_validate_json(
        json.dumps(
            {
                "upload_id": upload_id,
                "calibrated_at": "2025-04-01T12:34:56.789000+09:00",
            }
        )
    )

    resp = client.patch("/devices/SC/device_info", content=req.model_dump_json())
    assert resp.status_code == 200
    device = test_db.get(Device, "SC")
    assert device.calibrated_at == datetime(
        2025, 4, 1, 3, 34, 56, 789000, tzinfo=timezone.utc
    )


# TODO: add invalid test cases
# TODO: add test cases for handler
