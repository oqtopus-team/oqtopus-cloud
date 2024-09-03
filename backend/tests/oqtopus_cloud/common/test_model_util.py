from datetime import datetime

from oqtopus_cloud.common.model_util import model_to_dict, model_to_schema_dict
from oqtopus_cloud.common.models.device import Device


def _get_model_dict():
    return {
        "id": "SVSim",
        "device_type": "QPU",
        "status": "AVAILABLE",
        "restart_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_tasks": 8,
        "n_qubits": 39,
        "n_nodes": 512,
        "basis_gates": ["x", "sx", "rz", "cx"],
        "instructions": ["measure", "barrier", "reset"],
        "calibration_data": ["measure", "barrier", "reset"],
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56),
        "description": "State vector-based quantum circuit simulator",
    }


def test_model_to_dict():
    # Arrange
    expected = _get_model_dict()
    device = Device(**expected)

    # Act
    actual = model_to_dict(device)

    # Asseret
    assert actual == expected


def test_model_to_schema_dict():
    # Arrange
    model_dict = _get_model_dict()
    device = Device(**model_dict)

    # "description" is not mapped
    map_model_to_schema = {
        "id": "deviceId",  # transform field name
        "device_type": "deviceType",  # transform field name
        "status": "status",
        "restart_at": "restart_at",
        "pending_tasks": "pending_tasks",
        "n_qubits": "n_qubits",
        "n_nodes": "n_nodes",
        "basis_gates": "basis_gates",
        "instructions": "instructions",
        "calibration_data": "calibration_data",
        "calibrated_at": "calibrated_at",
    }

    # Act
    actual = model_to_schema_dict(device, map_model_to_schema)

    # Assert
    expected = _get_model_dict()
    expected["deviceId"] = expected["id"]
    del expected["id"]
    expected["deviceType"] = expected["device_type"]
    del expected["device_type"]
    del expected["description"]

    assert actual == expected
