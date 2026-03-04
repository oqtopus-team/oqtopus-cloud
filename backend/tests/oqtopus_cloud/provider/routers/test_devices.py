import json
from datetime import datetime, timezone
from typing import Dict

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.provider.lambda_function import app
from oqtopus_cloud.provider.routers.devices import (
    update_device,
    update_device_calibration,
    update_device_status,
)
from oqtopus_cloud.provider.schemas.devices import (
    DeviceDataUpdateResponse,
    DeviceInfoUpdate,
    DeviceStatusUpdate,
    UpdateDeviceRequest,
    UpdateDeviceResponse,
)
from oqtopus_cloud.provider.schemas.devices import Status as DeviceStatus
from zoneinfo import ZoneInfo

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
        "device_info": "{}",
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
        "device_info": "{}",
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
    assert device_aft.device_info == device_bef.device_info
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


def test_update_device_calibration(test_db):
    # Arrange
    test_db.add(_get_model_qpu())
    test_db.commit()
    device = test_db.get(Device, "SC")
    # Act
    request = DeviceInfoUpdate(
        device_info=json.dumps(_get_calibration_dict()),
        calibrated_at=datetime.now(ZoneInfo("Asia/Tokyo")),
    )
    actual = update_device_calibration(device_id=device.id, request=request, db=test_db)
    # Assert
    expected = DeviceDataUpdateResponse(message="Device's data updated")
    assert actual == expected


def test_update_device_info_timezone(test_db):
    # Arrange
    test_db.add(_get_model_qpu())
    test_db.commit()

    req = DeviceInfoUpdate.model_validate_json(
        '{ "device_info": "{}", "calibrated_at": "2025-04-01T12:34:56.789000+09:00" }'
    )

    resp = client.patch("/devices/SC/device_info", content=req.model_dump_json())
    assert resp.status_code == 200
    device = test_db.get(Device, "SC")
    assert device.calibrated_at == datetime(
        2025, 4, 1, 3, 34, 56, 789000, tzinfo=timezone.utc
    )


# TODO: add invalid test cases
# TODO: add test cases for handler
