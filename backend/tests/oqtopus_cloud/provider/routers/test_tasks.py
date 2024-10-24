import json
import uuid
from datetime import datetime
from typing import Dict

from oqtopus_cloud.common.models.device import (
    Device,
)
from oqtopus_cloud.common.models.task import (
    Task,
)
from oqtopus_cloud.provider.routers.tasks import (
    get_task,
    get_tasks,
    update_task,
)
from oqtopus_cloud.provider.schemas.tasks import (
    Action,
    InternalTaskStatus,
    SamplingAction,
    TaskId,
    TaskInfo,
    TaskStatusUpdate,
    TaskStatusUpdateResponse,
)
from zoneinfo import ZoneInfo

# sqlite does not support jst timezone
# utc = ZoneInfo("UTC")
utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")


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


def _get_device_model():
    mode_dict = {
        "id": "SC2",
        "device_type": "QPU",
        "status": "AVAILABLE",
        "restart_at": datetime(2023, 1, 2, 12, 34, 56),
        "pending_tasks": 8,
        "n_qubits": 39,
        "n_nodes": 512,
        "basis_gates": '["x", "sx", "rz", "cx"]',
        "instructions": '["measure", "barrier", "reset"]',
        "calibration_data": json.dumps(_get_calibration_dict()),  # str
        "calibrated_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        "description": "State vector-based quantum circuit simulator",
    }
    return Device(**mode_dict)


def _get_task_model(task_dict=None):
    if task_dict is None:
        task_dict = {
            "id": uuid.UUID("e8a60c14-8838-46c9-816a-30191d6ab517").bytes,
            "name": "Test task 3",
            "owner": "admin",
            "code": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
            "action": "sampling",
            "shots": 1024,
            "device": "SC2",
            "n_qubits": 64,
            "n_nodes": 112,
            "qubit_allocation": None,
            "skip_transpilation": True,
            "seed_transpilation": None,
            "seed_simulation": None,
            "ro_error_mitigation": None,
            "n_per_node": None,
            "simulation_opt": None,
            "status": "QUEUED",
            "created_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
        }
    return Task(**task_dict)


def test_get_tasks(test_db):
    # Arrange
    test_db.add(_get_task_model(task_dict=None))
    test_db.add(_get_device_model())
    test_db.commit()
    deviceId = "SC2"
    actual = get_tasks(deviceId=deviceId, db=test_db)
    # Assert
    expected = [
        TaskInfo(
            taskId=TaskId(root=uuid.UUID("e8a60c14-8838-46c9-816a-30191d6ab517")),
            code='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
            device="SC2",
            nQubits=64,
            nNodes=112,
            action=Action(SamplingAction(name="sampling", nShots=1024)),
            qubitAllocation=None,
            skipTranspilation=True,
            seedTranspilation=None,
            seedSimulation=None,
            roErrorMitigation=None,
            nPerNode=None,
            simulationOpt=None,
            status=InternalTaskStatus("QUEUED"),
            createdAt=datetime(2024, 3, 4, 12, 34, 56, tzinfo=jst),
        )
    ]
    assert actual == expected


def test_get_task(test_db):
    # Arrange

    test_db.add(_get_task_model(task_dict=None))
    test_db.add(_get_device_model())
    test_db.commit()
    taskId = "e8a60c14-8838-46c9-816a-30191d6ab517"
    actual = get_task(taskId=taskId, db=test_db)
    # Assert
    expected = TaskInfo(
        taskId=TaskId(root=uuid.UUID("e8a60c14-8838-46c9-816a-30191d6ab517")),
        code='OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
        device="SC2",
        nQubits=64,
        nNodes=112,
        action=Action(SamplingAction(name="sampling", nShots=1024)),
        qubitAllocation=None,
        skipTranspilation=True,
        seedTranspilation=None,
        seedSimulation=None,
        roErrorMitigation=None,
        nPerNode=None,
        simulationOpt=None,
        status=InternalTaskStatus("QUEUED"),
        createdAt=datetime(2024, 3, 4, 12, 34, 56, tzinfo=jst),
    )

    assert actual == expected


def test_update_task(test_db):
    task_dict = {
        "id": uuid.UUID("e8a60c14-8838-46c9-816a-30191d6ab517").bytes,
        "owner": "admin",
        "code": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];',
        "action": "sampling",
        "shots": 1024,
        "device": "SC2",
        "n_qubits": 64,
        "n_nodes": 112,
        "qubit_allocation": None,
        "skip_transpilation": True,
        "seed_transpilation": None,
        "seed_simulation": None,
        "ro_error_mitigation": None,
        "n_per_node": None,
        "simulation_opt": None,
        "status": "QUEUED",
        "created_at": datetime(2024, 3, 4, 12, 34, 56, tzinfo=utc),
    }
    # Arrange
    test_db.add(_get_task_model(task_dict=task_dict))
    test_db.add(_get_device_model())
    test_db.commit()
    taskId = "e8a60c14-8838-46c9-816a-30191d6ab517"
    request = TaskStatusUpdate(status="RUNNING")
    actual = update_task(taskId=taskId, request=request, db=test_db)

    expected = TaskStatusUpdateResponse(message="Task status updated")
    # Assert

    assert actual == expected


# TODO: add invalid test cases
# TODO: add test cases for handler
