import json
from datetime import datetime, timezone
from typing import Dict

import pytz
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.provider.routers.devices import (
    update_device_calibration,
    update_device_status,
)
from oqtopus_cloud.provider.schemas.devices import (
    DeviceDataUpdateResponse,
    DeviceInfoUpdate,
    DeviceStatusUpdate,
)
from oqtopus_cloud.provider.schemas.devices import Status as DeviceStatus
from zoneinfo import ZoneInfo

# jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")


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


def test_update_device_status_available(test_db):
    # Arrange
    test_db.add(_get_model_sim())
    test_db.commit()
    device = test_db.get(Device, "SC2")
    # Act
    request = DeviceStatusUpdate(status=DeviceStatus.available, available_at=None)
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


# TODO: add invalid test cases
# TODO: add test cases for handler
