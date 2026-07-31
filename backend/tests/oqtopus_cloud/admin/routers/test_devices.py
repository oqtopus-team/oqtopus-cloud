import json
import os
from io import BytesIO
import zipfile
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from oqtopus_cloud.admin.lambda_function import app
from oqtopus_cloud.admin.schemas.devices import (
    DeviceInfo,
    DeviceType,
    Status,
)
from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.device_info_history import DeviceInfoHistory
from oqtopus_cloud.common.storages import FSSpecStorage
from oqtopus_cloud.common.storages.storage_utils import get_device_info_key
from pydantic.type_adapter import TypeAdapter
from zoneinfo import ZoneInfo

client = TestClient(app)

utc = ZoneInfo("UTC")


def _device_info_archive_bytes(device_info: dict) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("device_info.json", json.dumps(device_info))
    return buf.getvalue()


def _put_device_info(storage: FSSpecStorage, device_id: str, device_info: dict) -> str:
    key = get_device_info_key(device_id)
    storage.put(key=key, data=_device_info_archive_bytes(device_info))
    return storage.get_download_presigned_url(key=key)


def _get_model(n, device_info=None):
    mode_dict = {
        "id": f"SVSim{n}",
        "device_type": "simulator",
        "status": "available",
        "available_at": datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
        "pending_jobs": n,
        "n_qubits": 1 + n,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "device_info": json.dumps(device_info) if device_info is not None else None,
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        "description": "State vector-based quantum circuit simulator",
        "created_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
    }
    return Device(**mode_dict)


def _get_history_model(
    device_id: str,
    calibrated_at: datetime,
    n_qubits: int,
    n_couplings: int,
) -> DeviceInfoHistory:
    return DeviceInfoHistory(
        history_uid=f"history-{device_id}-{calibrated_at:%Y%m%d%H%M%S}",
        device_id=device_id,
        calibrated_at=calibrated_at,
        n_qubits=n_qubits,
        n_couplings=n_couplings,
    )


def test_get_devices(
    test_db,
):
    """_summary_
    Simple GET /devices tests
    """
    device_info1 = {"device_id": "SVSim1"}
    device_info2 = {"device_id": "SVSim2"}
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    device_info_url1 = _put_device_info(storage, "SVSim1", device_info1)
    device_info_url2 = _put_device_info(storage, "SVSim2", device_info2)

    test_db.flush()
    test_db.add(_get_model(1, device_info1))
    test_db.add(_get_model(2, device_info2))
    test_db.commit()
    response = client.get("/devices")
    adapter = TypeAdapter(list[DeviceInfo])
    actual = adapter.validate_python(response.json())
    expected = [
        DeviceInfo(
            device_id="SVSim1",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            n_pending_jobs=1,
            n_qubits=2,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            device_info=device_info_url1,
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
            description="State vector-based quantum circuit simulator",
        ),
        DeviceInfo(
            device_id="SVSim2",
            device_type=DeviceType.simulator,
            status=Status.available,
            available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
            n_pending_jobs=2,
            n_qubits=3,
            basis_gates=["x", "sx", "rz", "cx"],
            supported_instructions=["measure", "barrier", "reset"],
            device_info=device_info_url2,
            calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
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
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    device_info_url = _put_device_info(storage, "SVSim1", device_info)

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
        available_at=datetime(2023, 1, 2, 12, 34, 56, tzinfo=utc),
        n_pending_jobs=1,
        n_qubits=2,
        basis_gates=["x", "sx", "rz", "cx"],
        supported_instructions=["measure", "barrier", "reset"],
        device_info=device_info_url,
        calibrated_at=datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
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


def test_list_device_histories(test_db):
    device_info = {"device_id": "SVSim1"}
    test_db.add(_get_model(1, device_info))
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc), 2, 1
        )
    )
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 5, 12, 34, 56, tzinfo=utc), 4, 3
        )
    )
    test_db.commit()

    response = client.get("/device_histories?device_id=SVSim1&limit=1")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "history_uid": "history-SVSim1-20240305123456",
                "device_id": "SVSim1",
                "calibrated_at": "2024-03-05T12:34:56Z",
                "n_qubits": 4,
                "n_couplings": 3,
            }
        ],
        "total": 2,
        "limit": 1,
        "offset": 0,
    }


def test_get_device_history(test_db):
    device_info = {"device_id": "SVSim1"}
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    history_key = "devices/SVSim1/history/20240304T123456000000Z/device_info.zip"
    storage.put(key=history_key, data=_device_info_archive_bytes(device_info))
    test_db.add(_get_model(1, device_info))
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc), 2, 1
        )
    )
    test_db.commit()

    response = client.get("/device_histories/history-SVSim1-20240304123456")

    assert response.status_code == 200
    assert response.json() == {
        "history_uid": "history-SVSim1-20240304123456",
        "device_id": "SVSim1",
        "calibrated_at": "2024-03-04T12:34:56Z",
        "n_qubits": 2,
        "n_couplings": 1,
        "device_info": f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}/{history_key}",
    }


def test_delete_device_history(test_db):
    device_info = {"device_id": "SVSim1"}
    history_key = "devices/SVSim1/history/20240304T123456000000Z/device_info.zip"
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    storage.put(key=history_key, data=_device_info_archive_bytes(device_info))
    test_db.add(_get_model(1, device_info))
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc), 2, 1
        )
    )
    test_db.commit()

    response = client.delete("/device_histories/history-SVSim1-20240304123456")

    assert response.status_code == 204
    assert (
        test_db.query(DeviceInfoHistory)
        .filter_by(history_uid="history-SVSim1-20240304123456")
        .first()
        is None
    )
    assert not storage.does_exist(key=history_key)


def test_delete_device_history_allows_missing_storage_object(test_db):
    device_info = {"device_id": "SVSim1"}
    test_db.add(_get_model(1, device_info))
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc), 2, 1
        )
    )
    test_db.commit()

    response = client.delete("/device_histories/history-SVSim1-20240304123456")

    assert response.status_code == 204
    assert (
        test_db.query(DeviceInfoHistory)
        .filter_by(history_uid="history-SVSim1-20240304123456")
        .first()
        is None
    )


def test_delete_device_history_404(test_db):
    device_info = {"device_id": "SVSim1"}
    test_db.add(_get_model(1, device_info))
    test_db.commit()

    response = client.delete("/device_histories/history-unknown")

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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device registered successfully"}
    # confirm the device is registered
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device.basis_gates == '["x", "sx", "rz", "cx", "t"]'
    assert device.device_info == json.dumps(device_info)


def test_register_devices_no_utc(
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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+09:00",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 400


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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
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
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "t"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
        "description": "State vector-based quantum circuit simulator",
    }

    response = client.post("/devices", json=body)
    assert response.status_code == 500


def test_update_device_data_full(
    test_db,
):
    """_summary_
    Simple PATCH /devices/{device_id} tests full update
    """

    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "device_type": "QPU",
        "status": "unavailable",
        "n_qubits": 4,
        "available_at": "2023-01-02T12:35:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx", "cy"],
        "supported_instructions": ["measure", "barrier"],
        "calibrated_at": "2024-03-04T12:54:56+00:00",
        "description": "State vector-based quantum circuit simulator updated",
    }

    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device updated successfully"}
    # confirm the device is updated
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device.device_type == "QPU"
    assert device.status == "unavailable"
    assert device.n_qubits == 4
    assert device.available_at == datetime(2023, 1, 2, 12, 35, 56, tzinfo=timezone.utc)
    assert device.basis_gates == '["x", "sx", "rz", "cx", "cy"]'
    assert device.instructions == '["measure", "barrier"]'
    assert device.calibrated_at == datetime(2024, 3, 4, 12, 54, 56, tzinfo=timezone.utc)
    assert device.description == "State vector-based quantum circuit simulator updated"


def test_update_device_data_partial(
    test_db,
):
    """_summary_
    Simple PATCH /devices/{device_id} tests partially update
    """

    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "n_qubits": 999,
        "description": "updated description",
    }
    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device updated successfully"}
    # confirm the device is updated
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device.description == "updated description"
    assert device.n_qubits == 999


def test_update_device_data_keeps_uploaded_device_info(
    test_db,
):
    device_info = {"device_id": "SVSim1"}
    device_info_key = get_device_info_key("SVSim1")
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    storage.put(key=device_info_key, data=_device_info_archive_bytes(device_info))

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "calibrated_at": "2024-03-04T12:34:56+00:00",
    }

    response = client.patch("/devices/SVSim1", json=body)

    assert response.status_code == 200
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert storage.does_exist(key=device_info_key)
    assert device.calibrated_at == datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc)


def test_update_device_data_timezone_awareness(
    test_db,
):
    """_summary_
    Simple PATCH /devices/{device_id} tests partially update
    """

    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    body = {
        "calibrated_at": "2024-03-04T12:34:56+09:00",
        "description": "State vector-based quantum circuit simulator updated",
    }

    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 200
    assert response.json() == {"message": "Device updated successfully"}
    # confirm the device is updated
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device.calibrated_at == datetime(2024, 3, 4, 3, 34, 56, tzinfo=timezone.utc)


def test_update_device_data_ignores_legacy_device_info_field(
    test_db,
):
    """Legacy device_info fields in PATCH should be ignored."""

    device_info = {"device_id": "SVSim1"}

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()
    device_info = {"device_id": "SVSim2"}
    body = {
        "device_info": json.dumps(device_info),
        "n_qubits": 999,
        "description": "updated description",
    }
    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 200
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device is not None
    assert device.n_qubits == 999
    assert device.description == "updated description"


def test_update_device_data_404(test_db):
    """_summary_
    Simple PATCH /devices/{device_id} tests 404 error
    """
    device_info = {"device_id": "SVSim1"}
    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()

    body = {
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 3,
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
        "description": "State vector-based quantum circuit simulator",
    }
    response = client.patch("/devices/SVSim2", json=body)
    assert response.status_code == 404


def test_update_device_data_500():
    """_summary_
    Simple PATCH /devices/{device_id} tests 500 error
    """
    body = {
        "device_type": "simulator",
        "status": "available",
        "n_qubits": 2,
        "available_at": "2023-01-02T12:34:56+00:00",
        "basis_gates": ["x", "sx", "rz", "cx"],
        "supported_instructions": ["measure", "barrier", "reset"],
        "calibrated_at": "2024-03-04T12:34:56+00:00",
        "description": "State vector-based quantum circuit simulator",
    }
    response = client.patch("/devices/SVSim1", json=body)
    assert response.status_code == 500


def test_delete_device(
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


def test_delete_device_deletes_uploaded_device_info(
    test_db,
):
    """DELETE should remove both the device row and uploaded device_info."""
    device_info = {"device_id": "SVSim1"}
    device_info_key = get_device_info_key("SVSim1")
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    storage.put(key=device_info_key, data=_device_info_archive_bytes(device_info))

    test_db.flush()
    test_db.add(_get_model(1, device_info))
    test_db.commit()

    response = client.delete("/devices/SVSim1")

    assert response.status_code == 204
    device = test_db.query(Device).filter(Device.id == "SVSim1").first()
    assert device is None
    assert not storage.does_exist(key=device_info_key)


def test_delete_device_deletes_device_info_history(test_db):
    device_info = {"device_id": "SVSim1"}
    history_key = "devices/SVSim1/history/20240304T123456000000Z/device_info.zip"
    storage = FSSpecStorage(fs_url=f"file://{os.environ['STORAGE_LOCAL_BASE_PATH']}")
    storage.put(key=history_key, data=_device_info_archive_bytes(device_info))
    test_db.add(_get_model(1, device_info))
    test_db.add(
        _get_history_model(
            "SVSim1", datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc), 2, 1
        )
    )
    test_db.commit()

    response = client.delete("/devices/SVSim1")

    assert response.status_code == 204
    assert (
        test_db.query(DeviceInfoHistory).filter_by(device_id="SVSim1").first() is None
    )
    assert not storage.does_exist(key=history_key)


def test_delete_device_404(
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


def test_delete_device_500():
    """_summary_
    Simple DELETE /devices/{device_id} tests 500 error
    """
    response = client.delete("/devices/SVSim1")
    assert response.status_code == 500
