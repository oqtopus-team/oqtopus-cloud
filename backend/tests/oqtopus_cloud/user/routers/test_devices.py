import json
from datetime import datetime
from typing import Any, Dict

import pytz
from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.user.routers.devices import get_device, get_devices, model_to_schema
from oqtopus_cloud.user.schemas.devices import DeviceInfo, DeviceType, Status
from oqtopus_cloud.user.schemas.errors import (
    ErrorResponse,
    ForbiddenErrorResponse,
    NotFoundErrorResponse,
)
from starlette.requests import Request
from zoneinfo import ZoneInfo

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


def _get_user_model(n: int, username: str, available_devices="*") -> User:
    if available_devices != "*":
        available_devices = json.dumps(available_devices)

    model_dict = {
        "id": n,
        "cognito_id": f"cognito_id_{n}",
        "email": f"email_{n}",
        "username": username,
        "userstatus": UserStatus.approved,
        "organization": f"organization_{n}",
        "group_id": f"group_id_{n}",
        "available_devices": available_devices,
        "api_token_id": None,
        "api_token_hash": None,
        "api_token_expiration": None,
        "created_at": datetime(2024, 3, 4, 12, 34, 57, tzinfo=utc),
        "updated_at": datetime(2024, 3, 4, 12, 34, 58, tzinfo=utc),
    }
    return User(**model_dict)


def _create_request(method="GET") -> Request:
    scope: Dict[str, Any] = {
        "type": "http",
        "method": method,
        "path": "/test",
        "headers": [],
    }

    return Request(scope=scope)


def _get_model(device="SVSim"):
    mode_dict = {
        "id": device,
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56, tzinfo=pytz.utc),
        "pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "device_info": "{}",
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=pytz.utc),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=pytz.utc),
    }
    return Device(**mode_dict)


def test_get_device(test_db):
    # Arrange
    user_no = 1
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user))
    test_db.add(_get_model())
    test_db.commit()

    # Act
    actual = get_device("SVSim", request, test_db)

    # Assert
    expected = DeviceInfo(
        device_id="SVSim",
        device_type=DeviceType.simulator,
        status=Status.available,
        available_at=pytz.utc.localize(datetime(2023, 1, 2, 12, 34, 56)),
        n_pending_jobs=8,
        n_qubits=39,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        # device_info=CalibrationData(**_get_calibration_dict()),
        device_info="{}",
        calibrated_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
        description="State vector-based quantum circuit simulator",
    )
    assert actual == expected


def test_can_get_device_if_in_available_devices(test_db):
    # Arrange
    user_no = 1
    device = "SC"
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user, available_devices=[device]))
    test_db.add(_get_model(device=device))
    test_db.commit()

    # Act
    actual = get_device(device, request, test_db)

    # Assert
    expected = DeviceInfo(
        device_id=device,
        device_type=DeviceType.simulator,
        status=Status.available,
        available_at=pytz.utc.localize(datetime(2023, 1, 2, 12, 34, 56)),
        n_pending_jobs=8,
        n_qubits=39,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        # device_info=CalibrationData(**_get_calibration_dict()),
        device_info="{}",
        calibrated_at=pytz.utc.localize(datetime(2024, 3, 4, 12, 34, 56)),
        description="State vector-based quantum circuit simulator",
    )
    assert actual == expected


def test_cannot_get_device_without_permission(test_db):
    # Arrange
    user_no = 1
    device = "SC"
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user, ["Kawasaki", "SVSim"]))
    test_db.add(_get_model(device=device))
    test_db.commit()

    # Act
    response = get_device(device, request, test_db)

    # Assert
    assert isinstance(response, ForbiddenErrorResponse)
    assert response.status_code == 403
    assert json.loads(response.body) == {
        "message_code": "FORBIDDEN_DEVICE_ACCESS",
        "message_params": {"id": device},
        "message": f"Forbidden: cannot access device_id={device}.",
    }


def test_cannot_get_device_that_not_exist(test_db):
    # Arrange
    user_no = 1
    device = "SC222"
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user))
    test_db.commit()

    # Act
    response = get_device(device, request, test_db)

    # Assert
    assert isinstance(response, NotFoundErrorResponse)
    assert response.status_code == 404
    assert json.loads(response.body) == {
        "message_code": "DEVICE_NOT_FOUND",
        "message_params": {"id": device},
        "message": f"device_id={device} is not found.",
    }


def test_can_only_get_devices_that_user_can_access(test_db):
    # Arrange
    user_no = 1
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user, ["Test_model", "SVSim"]))
    test_db.add(_get_model(device="SC"))
    test_db.add(_get_model(device="SVSim"))
    test_db.add(_get_model(device="Test_model"))
    test_db.commit()

    # Act
    actual = get_devices(request, test_db)

    # Assert
    expected = [
        DeviceInfo(
            device_id="SVSim",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=pytz.utc),
            n_pending_jobs=8,
            n_qubits=39,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            # calibrationData=CalibrationData(**_get_calibration_dict()),
            device_info="{}",
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=pytz.utc),
            description="State vector-based quantum circuit simulator",
        ),
        DeviceInfo(
            device_id="Test_model",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=pytz.utc),
            n_pending_jobs=8,
            n_qubits=39,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            # calibrationData=CalibrationData(**_get_calibration_dict()),
            device_info="{}",
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=pytz.utc),
            description="State vector-based quantum circuit simulator",
        ),
    ]

    assert actual == expected


def test_can_return_all_devices_when_user_has_access_to_all_devices(test_db):
    # Arrange
    user_no = 1
    user = "test_user"
    request = _create_request()
    request.state.owner = f"email_{user_no}"

    test_db.add(_get_user_model(user_no, user, "*"))
    test_db.add(_get_model(device="SC"))
    test_db.add(_get_model(device="SVSim"))
    test_db.add(_get_model(device="Test_model"))
    test_db.commit()

    # Act
    devices = get_devices(request, test_db)

    # Assert
    assert not isinstance(devices, ErrorResponse)
    assert any(device.device_id == "Kawasaki" for device in devices)
    assert any(device.device_id == "SC" for device in devices)
    assert any(device.device_id == "SVSim" for device in devices)
    assert any(device.device_id == "Test_model" for device in devices)


def test_model_to_shema():
    # Arrange
    model = _get_model()

    # Act
    actual = model_to_schema(model)

    # Assert
    expected = DeviceInfo(
        device_id="SVSim",
        device_type=DeviceType.simulator,
        status=Status.available,
        available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=pytz.utc),
        n_pending_jobs=8,
        n_qubits=39,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        # calibrationData=CalibrationData(**_get_calibration_dict()),
        device_info="{}",
        calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=pytz.utc),
        description="State vector-based quantum circuit simulator",
    )
    assert actual == expected


def test_get_device_handler(test_client, test_db):
    # Arrange
    test_db.add(_get_user_model(1, "admin"))
    test_db.add(_get_model())
    test_db.commit()

    # Act
    actual = test_client.get("/devices/SVSim")
    assert actual.status_code == 200
    # Assert
    expected = {
        "device_id": "SVSim",
        "device_type": "simulator",
        "status": "available",
        "available_at": "2023-01-02T12:34:56Z",
        "n_pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": ["x", "sx", "rz", "cx"],
        "supported_instructions": ["measure", "barrier", "reset"],
        # "calibrationData": _get_calibration_dict(),
        "device_info": "{}",
        "calibrated_at": "2024-03-04T12:34:56Z",
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
