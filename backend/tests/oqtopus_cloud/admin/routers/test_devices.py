import json
import logging
from datetime import datetime

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.devices import (
    DeviceBase,
    DeviceInfo,
    DeviceType,
    Status,
)
from oqtopus_cloud.common.models.device import Device
from pydantic.type_adapter import TypeAdapter

logger = logging.getLogger(__name__)

client = TestClient(app)


def _get_model(n, device_info={}):
    mode_dict = {
        "id": f"SVSim{n}",
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_jobs": n,
        "n_qubits": 1 + n,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "device_info": json.dumps(device_info),
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56),
    }
    return Device(**mode_dict)


def test_get_devices(
    test_db,
):
    """_summary_
    Simple GET /devices tests
    """
    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.add(_get_model(2, device_info))
    test_db.commit()
    response = client.get("/devices")
    adapter = TypeAdapter(list[DeviceInfo])
    actual = adapter.validate_python(response.json())
    expected = [
        DeviceInfo(
            device_id="SVSim1",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56),
            n_pending_jobs=1,
            n_qubits=2,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            device_info=json.dumps(device_info),
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56),
            description="State vector-based quantum circuit simulator",
        ),
        DeviceInfo(
            device_id="SVSim2",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56),
            n_pending_jobs=2,
            n_qubits=3,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            device_info=json.dumps(device_info),
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56),
            description="State vector-based quantum circuit simulator",
        ),
    ]
    assert response.status_code == 200
    assert actual == expected


def test_get_devices_500():
    """_summary_
    Simple GET /devices tests 500 error
    """
    response = client.get("/devices")
    assert response.status_code == 500


def test_get_device(
    test_db,
):
    """_summary_
    Simple GET /devices/{device_id} tests
    """
    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    response = client.get("/devices/SVSim1")
    adapter = TypeAdapter(DeviceInfo)
    actual = adapter.validate_python(response.json())
    expected = DeviceInfo(
        device_id="SVSim1",
        device_type=DeviceType.simulator,
        status=Status.available,
        available_at=datetime(2023, 1, 2, 12, 34, 56),
        n_pending_jobs=1,
        n_qubits=2,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        device_info=json.dumps(device_info),
        calibrated_at=datetime(2024, 3, 4, 12, 34, 56),
        description="State vector-based quantum circuit simulator",
    )
    assert response.status_code == 200
    assert actual == expected


def test_get_device_500():
    """_summary_
    Simple GET /devices/{device_id} tests 500 error
    """
    response = client.get("/devices/1")
    assert response.status_code == 500


def test_get_device_no_device(
    test_db,
):
    """_summary_
    Simple GET /devices/{device_id} tests with no device
    """
    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    response = client.get("/devices/SVSim2")
    assert response.status_code == 404


def test_register_devices(
    test_db,
):
    """_summary_
    Simple POST /devices tests
    """
    device_info = {"device_id": "SVSim1"}

    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx", "t"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device registered successfully"}
    # confirm the device is registered
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device.basis_gates == '"[\\"x\\", \\"sx\\", \\"rz\\", \\"cx\\", \\"t\\"]"'


def test_register_devices_no_device_id_400(
    test_db,
):
    """_summary_
    Simple POST /devices tests 400 error no device id
    """
    body = {
        "device_info": None,
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx", "t"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 400
    assert response.json() == {"message": "device_id is required"}


def test_register_devices_device_id_exception_400(
    test_db,
):
    """_summary_
    Simple POST /devices tests 400 error no device id
    """
    body = {
        "device_info": "not json format info",
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx", "t"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 400
    assert response.json() == {"message": "device_id is required"}


def test_register_devices_400(
    test_db,
):
    """_summary_
    Simple POST /devices tests 400 error
    """
    device_info = {"device_id_none": "SVSim1"}

    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx", "t"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 400
    assert response.json() == {"message": "device_id is required"}


def test_register_devices_overlap(
    test_db,
):
    """_summary_
    Simple POST /devices tests with overlapping device_id
    """
    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 400
    assert response.json() == {"message": "device_id=SVSim1 already exists"}


def test_register_devices_500():
    """_summary_
    Simple POST /devices tests 500 error
    """
    device_info = {"device_id": "SVSim1"}

    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx", "t"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 500


def test_update_devices_full(
    test_db,
):
    """_summary_
    Simple PATCH /devices/{device_id} tests
    """

    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }
    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device updated successfully"}


def test_update_devices_404(test_db):
    """_summary_
    Simple PATCH /devices/{device_id} tests 404 error
    """
    device_info = {"device_id": "SVSim1"}
    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()

    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 3,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }
    response = client.patch("/devices/SVSim2", json=body)
    assert response.status_code == 404


def test_update_devices_500():
    """_summary_
    Simple PATCH /devices/{device_id} tests 500 error
    """
    device_info = {"device_id": "SVSim1"}

    body = {
        "device_info": json.dumps(device_info),
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56",
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "supported_instructions": '["measure", "barrier", "reset"]',
        "calibrated_at": "2024-03-04T12:34:56",
        "description": "State vector-based quantum circuit simulator",
    }
    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 500


def test_delete_devices(
    test_db,
):
    """_summary_
    Simple DELETE /devices/{device_id} tests
    """
    device_info = {"device_id": "SVSim1"}
    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    response = client.delete("/devices/SVSim1")
    assert response.status_code == 204
    # confirm the device is deleted
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device is None


def test_delete_devices_404(
    test_db,
):
    """_summary_
    Simple DELETE /devices/{device_id} tests 404 error
    """
    device_info = {"device_id": "SVSim1"}
    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    response = client.delete("/devices/SVSim2")
    assert response.status_code == 404


def test_delete_devices_500():
    """_summary_
    Simple DELETE /devices/{device_id} tests 500 error
    """
    response = client.delete("/devices/SVSim1")
    assert response.status_code == 500
