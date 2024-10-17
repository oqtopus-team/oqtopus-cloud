import json
from datetime import datetime
from typing import Dict

from fastapi.testclient import TestClient
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.user.lambda_function import app
from oqtopus_cloud.user.routers.devices import get_device, model_to_schema
from oqtopus_cloud.user.schemas.devices import DeviceInfo
from zoneinfo import ZoneInfo

jst = ZoneInfo("Asia/Tokyo")
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


"""
def _get_calibration_data() -> CalibrationData:
    calib = CalibrationData(
        qubitConnectivity=["(1,4)", "(4,5)", "(5,8)"],
        t1={"0": 55.51, "1": 37.03, "2": 57.13},
        t2={"0": 99.31, "1": 111.03, "2": 30.12},
        roError={"0": 0.0467, "1": 0.18, "2": 0.355},
        gateError={"sx": {"0": 0.00692, "1": 0.00296, "2": 0.072}},
        measProb0As1={"0": 0.00608, "1": 0.012, "2": 0.248},
        measProb1As0={"0": 0.0281, "1": 0.386, "2": 0.0811},
        gateDuration={"sx": {"0": 29.3, "1": 50.9, "2": 45.4}},
    )
    print(calib)
    return calib
"""


def _get_model():
    mode_dict = {
        "id": "SVSim",
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_jobs": 8,
        "n_qubits": 39,
        "n_nodes": 512,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        #"calibration_data": json.dumps(_get_calibration_dict()),  # str
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
    }
    return Device(**mode_dict)


def test_get_device(test_db):
    # Arrange
    test_db.add(_get_model())
    test_db.commit()

    # Act
    actual = get_device("SVSim", test_db)

    # Assert
    expected = DeviceInfo(
        device_id="SVSim",
        device_type="simulator",
        status="available",
        available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=jst),
        n_pending_tasks=8,
        n_qubits=39,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        #device_info=CalibrationData(**_get_calibration_dict()),
        device_info="",
        calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=jst),
        description="State vector-based quantum circuit simulator",
    )
    assert actual == expected


def test_model_to_shema():
    # Arrange
    model = _get_model()

    # Act
    actual = model_to_schema(model)

    # Assert
    expected = DeviceInfo(
        device_id="SVSim",
        device_type="simulator",
        status="available",
        available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=jst),
        n_pending_tasks=8,
        n_qubits=39,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        #calibrationData=CalibrationData(**_get_calibration_dict()),
        device_info="",
        calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=jst),
        description="State vector-based quantum circuit simulator",
    )
    assert actual == expected


def test_get_device_hadler(test_db):
    # Arrange
    test_db.add(_get_model())
    test_db.commit()

    # Act
    actual = client.get("/devices/SVSim")
    assert actual.status_code == 200
    # Assert
    expected = {
        "device_id": "SVSim",
        "device_type": "simulator",
        "status": "available",
        "available_at": "2023-01-02T12:34:56+09:00",
        "n_pending_tasks": 8,
        "n_qubits": 39,
        "basis_gates": ["x", "sx", "rz", "cx"],
        "supported_instructions": ["measure", "barrier", "reset"],
        #"calibrationData": _get_calibration_dict(),
        "device_info": "",
        "calibrated_at": "2024-03-04T12:34:56+09:00",
        "description": "State vector-based quantum circuit simulator",
    }
    assert actual.json() == expected


"""
def test_get_task_404(
    test_db,
):
    print(test_db)  # => 1
    response = client.get("/tasks/e8a60c14-8838-46c9-816a-30191d6ab517")
    assert response.status_code == 404
    assert response.json() == {"detail": "task not found with the given id"}


def test_get_task_200(
    test_db,
):
    device = Device(
        id="1",
        device_type="simulator",
        status="AVAILABLE",
        n_qubits=1,
        n_nodes=1,
        basis_gates="basis_gates",
        instructions="instructions",
        description="description",
    )
    test_db.add(device)
    test_db.flush()
    test_db.commit()
    response = client.get("/tasks/e8a60c14-8838-46c9-816a-30191d6ab517")
    assert response.status_code == 200
    assert response.json() == {
        "taskId": "e8a60c14-8838-46c9-816a-30191d6ab517",
        "code": "code",
        "device": "1",
        "nQubits": 1,
        "qubitAllocation": None,
        "nNodes": 1,
        "skipTranspilation": False,
        "simulationOpt": None,
        "seedTranspilation": 1,
        "seedSimulation": 1,
        "roErrorMitigation": "none",
        "nPerNode": 1,
    }
"""
