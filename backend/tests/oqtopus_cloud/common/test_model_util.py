from datetime import datetime

from oqtopus_cloud.common.model_util import model_to_dict, model_to_schema_dict
from oqtopus_cloud.common.models.device import Device


def _get_model_dict():
    return {
        "id": "SVSim",
        "device_type": "simulator",
        "status": "AVAILABLE",
        "available_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_jobs": 8,
        "n_qubits": 39,
        "basis_gates": ["x", "sx", "rz", "cx"],
        "instructions": ["measure", "barrier", "reset"],
        "device_info": "{'n_nodes': 512, 'calibration_data': {'qubit_connectivity': ['(1,4)', '(4,5)', '(5,8)'], 't1': {'0': 55.51, '1': 37.03, '2': 57.13}}",
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
        "id": "device_id",  # transform field name
        "device_type": "deviceType",  # transform field name
        "status": "status",
        "available_at": "available_at",
        "pending_jobs": "pending_jobs",
        "n_qubits": "n_qubits",
        "basis_gates": "basis_gates",
        "instructions": "instructions",
        "device_info": "device_info",
        "calibrated_at": "calibrated_at",
    }

    # Act
    actual = model_to_schema_dict(device, map_model_to_schema)

    # Assert
    expected = _get_model_dict()
    expected["device_id"] = expected["id"]
    del expected["id"]
    expected["deviceType"] = expected["device_type"]
    del expected["device_type"]
    del expected["description"]

    assert actual == expected
