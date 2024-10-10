import re
import uuid
from ast import literal_eval
from datetime import datetime
from typing import Any, Literal, Optional, Tuple

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from fastapi import Request as Event
from pydantic import ValidationError
from sqlalchemy.orm import (
    Session,
)
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.device import Device
from oqtopus_cloud.common.models.result import Result
from oqtopus_cloud.common.models.task import Task
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.success import SuccessResponse
from oqtopus_cloud.user.schemas.tasks import (
    EstimationTaskDef,
    EstimationTaskInfo,
    GetEstimationTaskStatusResponse,
    GetSamplingTaskStatusResponse,
    Operator,
    SamplingTaskDef,
    SamplingTaskInfo,
    SubmitTaskResponse,
    TaskId,
    TaskStatus,
)

from . import LoggerRouteHandler

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


class BadRequest(Exception):
    def __init__(self, detail: str):
        self.detail = detail


def create_sampling_task_info(task: Task) -> SamplingTaskInfo:
    status = task.status
    if task.status == "QUEUED_FETCHED":
        status = "QUEUED"
    elif task.status == "CANCELIING_FETCHED":
        status = "CANCELLING"
    return SamplingTaskInfo(
        taskId=TaskId(task.id),
        code=task.code,
        name=task.name,
        device=task.device,
        nQubits=task.n_qubits,
        nNodes=task.n_nodes,
        nShots=task.shots,
        qubitAllocation=task.qubit_allocation,
        skipTranspilation=task.skip_transpilation,
        seedTranspilation=task.seed_transpilation,
        seedSimulation=task.seed_simulation,
        roErrorMitigation=task.ro_error_mitigation,
        nPerNode=task.n_per_node,
        simulationOpt=task.simulation_opt,
        note=task.note,
        status=TaskStatus(root=status),  # type: ignore
        createdAt=task.created_at.astimezone(jst),
    )


def serialize_operator(operator: Operator) -> str | BadRequestResponse:
    pauli_regex = re.compile("([X|Y|Z|I]\\s+\\d+)(\\s+[X|Y|Z|I]\\s+\\d+)*\\s*$")
    ops = literal_eval(operator.model_dump_json())
    if not isinstance(ops, list) or len(ops) == 0:
        return BadRequestResponse(detail=f"Malformed operator format: {str(ops)}")
    for op in ops:
        if not isinstance(op, list) or len(op) != 2:
            return BadRequestResponse(f"Malformed operator format: {str(op)}")
        pauli_str = op[0]
        if not isinstance(pauli_str, str):
            return BadRequestResponse(
                f"Malformed operator format: malformed Pauli string: {str(op)}"
            )
        if not pauli_regex.match(pauli_str):
            return BadRequestResponse(
                f"Malformed operator format: malformed Pauli string: {str(op)}"
            )
        coef = op[1]
        try:
            if isinstance(coef, list):
                if len(coef) == 2:
                    op[1] = [float(coef[0]), float(coef[1])]
                elif len(coef) == 1:
                    op[1] = [float(coef[0]), 0.0]
                else:
                    return BadRequestResponse(
                        f"Malformed operator format: malformed coef value: {str(op)}"
                    )
            else:
                op[1] = [float(coef), 0.0]
        except (TypeError, ValueError):
            return BadRequestResponse(
                f"Malformed operator format: malformed coef value: {str(op)}"
            )
    return str(ops)


def create_estimation_task_info(task: Task) -> EstimationTaskInfo:
    status = task.status
    if task.status == "QUEUED_FETCHED":
        status = "QUEUED"
    elif task.status == "CANCELIING_FETCHED":
        status = "CANCELLING"

    return EstimationTaskInfo(
        taskId=TaskId(task.id),
        code=task.code,
        name=task.name,
        device=task.device,
        nQubits=task.n_qubits,
        nNodes=task.n_nodes,
        method=task.method,  # type: ignore
        nShots=task.shots,
        operator=Operator(literal_eval(task.operator)),  # type: ignore
        qubitAllocation=task.qubit_allocation,
        skipTranspilation=task.skip_transpilation,
        seedTranspilation=task.seed_transpilation,
        seedSimulation=task.seed_simulation,
        roErrorMitigation=task.ro_error_mitigation,
        nPerNode=task.n_per_node,
        simulationOpt=task.simulation_opt,
        note=task.note,
        status=TaskStatus(root=status),  # type: ignore
        createdAt=task.created_at.astimezone(jst),
    )


@router.get(
    "/tasks/sampling",
    response_model=list[SamplingTaskInfo],
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_sampling_tasks(
    event: Event,
    db: Session = Depends(get_db),
) -> list[SamplingTaskInfo] | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        tasks = (
            db.query(Task)
            .filter(Task.action == "sampling", Task.owner == owner)
            .order_by(Task.created_at)
            .all()
        )
        return [create_sampling_task_info(task) for task in tasks]
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


def validate_name(request: SamplingTaskDef | EstimationTaskDef) -> str | None:
    if request.name is not None:
        request.name
    return None


def validate_qubit_allocation(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> dict[str, int] | ErrorResponse | None:
    if request.qubitAllocation is not None:
        if device_info.device_type != "QPU":
            return BadRequestResponse(
                detail="qubitAllocation is valid only for QPU devices"
            )
        return request.qubitAllocation
    return None


def validate_skip_transpilation(request: SamplingTaskDef | EstimationTaskDef) -> bool:
    return (
        request.skipTranspilation if (request.skipTranspilation is not None) else False
    )


def validate_seed_transpilation(
    request: SamplingTaskDef | EstimationTaskDef,
) -> int | ErrorResponse | None:
    if request.seedTranspilation is not None:
        if request.skipTranspilation:
            return BadRequestResponse(
                detail="seedTranspilation is valid only for transpilation enabled tasks"
            )
        return request.seedTranspilation
    return None


def validate_seed_simulation(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> int | ErrorResponse | None:
    if request.seedSimulation is not None:
        if device_info.device_type != "simulator":
            return BadRequestResponse(
                detail="seedSimulation is valid only for simulator devices"
            )
        return request.seedSimulation
    return None


def validate_ro_error_mitigation(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> Literal["none", "pseudo_inverse", "least_square"] | ErrorResponse | None:
    if request.roErrorMitigation is not None and request.roErrorMitigation != "none":
        if device_info.device_type != "QPU":
            return BadRequestResponse(
                detail="roErrorMitigation is valid only for QPU devices"
            )
        return request.roErrorMitigation
    if device_info.device_type != "QPU":
        return None
    return "none"


def validate_n_per_node(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> int | ErrorResponse | None:
    if request.nPerNode is not None:
        if device_info.device_type != "simulator":
            return BadRequestResponse(
                detail="nPerNode is valid only for simulator devices"
            )
        return request.nPerNode
    if device_info.device_type != "simulator":
        return None
    return 1


def validate_simulation_opt(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> dict[str, Any] | ErrorResponse | None:
    if request.simulationOpt is not None:
        if device_info.device_type != "simulator":
            return BadRequestResponse(
                detail="simulationOpt is valid only for simulator devices"
            )
        return request.simulationOpt
    return None


def validate_note(
    request: SamplingTaskDef | EstimationTaskDef,
) -> str | None:
    return request.note if (request.note is not None) else None


def get_resources(
    request: SamplingTaskDef | EstimationTaskDef, device_info: Device
) -> Tuple[Optional[int], Optional[int]] | BadRequestResponse:
    n_qubits = None
    n_nodes = None

    if device_info.device_type == "simulator":
        if (request.nQubits is not None) and (request.nNodes is not None):
            return BadRequestResponse(
                detail="nQubits and nNodes parameters are exclusive"
            )

        if request.nQubits is not None:
            n_qubits = request.nQubits
            if n_qubits > device_info.n_qubits:
                return BadRequestResponse(
                    detail=f"Requested nQubits: {n_qubits} exceeds limit for device {device_info.id} (limit = {device_info.n_qubits})"
                )

        else:
            n_nodes = 1
            if request.nNodes is not None:
                n_nodes = request.nNodes
                if n_nodes > device_info.n_nodes:
                    return BadRequestResponse(
                        detail=f"Requested nNodes: {n_nodes} exceeds limit for device {device_info.id} (limit = {device_info.n_nodes})"
                    )

    else:  # QPU
        if request.nQubits is not None:
            n_qubits = request.nQubits
            if n_qubits > device_info.n_qubits:
                return BadRequestResponse(
                    detail=f"Requested nQubits: {n_qubits} exceeds limit for device {device_info.id} (limit = {device_info.n_qubits})"
                )
        if request.nNodes is not None:
            return BadRequestResponse(
                detail=f"nNodes parameter not supported for device: '{device_info.id}' (deviceType: {device_info.device_type}). nNodes requires deviceType: 'simulator'."
            )

    return (n_qubits, n_nodes)


@router.post(
    "/tasks/sampling",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmitTaskResponse,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def submit_sampling_tasks(
    event: Event,
    request: SamplingTaskDef,
    db: Session = Depends(get_db),
) -> SubmitTaskResponse | ErrorResponse:
    try:
        device_info = db.get(Device, request.device)  # type: ignore
        if device_info is None:
            return BadRequestResponse(detail="device not found")
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        if device_info.status != "AVAILABLE":
            return BadRequestResponse(f"device {device_info.id} is not available")

        # NOTE: method and operator is validated by pydantic
        shots = request.nShots
        # name is optional
        name = validate_name(request)
        code = request.code

        # NOTE:omit query from user_limits table logic
        resource = get_resources(request, device_info)
        if isinstance(resource, BadRequestResponse):
            return resource
        else:
            n_qubits, n_nodes = resource

        # qubit allocation is valid only for QPU devices
        qubit_allocation = validate_qubit_allocation(request, device_info)
        if isinstance(qubit_allocation, BadRequestResponse):
            return qubit_allocation

        # skip transpilation is False by default
        skip_transpilation = validate_skip_transpilation(request)
        if isinstance(skip_transpilation, BadRequestResponse):
            return skip_transpilation

        # seed transpilation is valid only for transpilation enabled tasks
        seed_transpilation = validate_seed_transpilation(request)
        if isinstance(seed_transpilation, BadRequestResponse):
            return seed_transpilation

        # seed simulation is valid only for simulator devices
        seed_simulation = validate_seed_simulation(request, device_info)
        if isinstance(seed_simulation, BadRequestResponse):
            return seed_simulation

        # ro error mitigation is valid only for QPU devices
        ro_error_mitigation = validate_ro_error_mitigation(request, device_info)
        if isinstance(ro_error_mitigation, BadRequestResponse):
            return ro_error_mitigation

        # n per node is valid only for simulator devices
        n_per_node = validate_n_per_node(request, device_info)
        if isinstance(n_per_node, BadRequestResponse):
            return n_per_node

        # simulation opt is valid only for simulator devices
        simulation_opt = validate_simulation_opt(request, device_info)
        if isinstance(simulation_opt, BadRequestResponse):
            return simulation_opt

        # note is optional
        note = validate_note(request)

        task = Task(
            id=uuid.uuid4().bytes,
            owner=owner,
            name=name,
            device=request.device,
            n_nodes=n_nodes,
            n_qubits=n_qubits,
            code=code,
            action="sampling",
            method=None,  # sampling task is not using method
            shots=shots,
            operator=None,  # sampling task is not using operator
            qubit_allocation=qubit_allocation,
            skip_transpilation=skip_transpilation,
            seed_transpilation=seed_transpilation,
            seed_simulation=seed_simulation,
            ro_error_mitigation=ro_error_mitigation,
            n_per_node=n_per_node,
            simulation_opt=simulation_opt,
            note=note,
            created_at=datetime.now(),
        )

        db.add(task)
        db.commit()

        task_get = db.get(Task, task.id)
        if task_get is None:
            return NotFoundErrorResponse(
                detail=f"the created task {task.id} is not found"
            )

        return SubmitTaskResponse(
            taskId=task.id,
            createdAt=task.created_at.astimezone(jst),
            status=task_get.status,
        )
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/tasks/sampling/{taskId}",
    response_model=SamplingTaskInfo,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_sampling_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> SamplingTaskInfo | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        task = (
            db.query(Task)
            .filter(Task.id == task_id, Task.owner == owner, Task.action == "sampling")
            .first()
        )
        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")
        return create_sampling_task_info(task)
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.delete(
    "/tasks/sampling/{taskId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def delete_sampling_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> None | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        task = db.get(Task, task_id)

        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")

        if (
            task.owner != owner
            or task.action != "sampling"
            or task.status not in ["COMPLETED", "FAILED", "CANCELLED"]
        ):
            return NotFoundErrorResponse(
                detail=f"{taskId} task is not in valid status for deletion (valid statuses for deletion: 'COMPLETED', 'FAILED' and 'CANCELLED')"
            )

        db.delete(task)
        db.commit()
        return
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/tasks/sampling/{taskId}/status",
    response_model=GetSamplingTaskStatusResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_sampling_task_status(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> GetSamplingTaskStatusResponse | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    owner = event.state.owner
    logger.info("invoked!", extra={"owner": owner})
    task = (
        db.query(Task.id, Task.status)
        .filter(
            Task.id == uuid.UUID(taskId).bytes,
            Task.action == "sampling",
            Task.owner == owner,
        )
        .first()
    )
    if task is None:
        return NotFoundErrorResponse(detail="task not found with the given id")
    return GetSamplingTaskStatusResponse(
        taskId=TaskId(uuid.UUID(taskId)), status=TaskStatus(root=task.status)
    )


@router.post(
    "/tasks/sampling/{taskId}/cancel",
    response_model=SuccessResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def cancel_sampling_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        task = db.get(Task, task_id)

        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")
        if (
            task.owner != owner
            or task.action != "sampling"
            or task.status not in ["QUEUED_FETCHED", "QUEUED", "RUNNING"]
        ):
            return NotFoundErrorResponse(
                detail=f"{taskId} task is not in valid status for cancellation (valid statuses for cancellation: 'QUEUED_FETCHED', 'QUEUED' and 'RUNNING')"
            )
        if task.status == "QUEUED":
            logger.info("task is in QUEUED state, so it will be cancelled")
            result = Result(
                task_id=task_id, status="CANCELLED", reason="user cancelled"
            )
            db.add(result)
            db.commit()
        elif task.status in ["QUEUED_FETCHED", "RUNNING"]:
            logger.info(
                "task is in QUEUED_FETCHED or RUNNING state, so it will be marked as CANCELLING"
            )
            task.status = "CANCELLING"
            db.commit()
        return SuccessResponse(message="cancel request accepted")
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/tasks/estimation",
    response_model=list[EstimationTaskInfo],
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_estimation_tasks(
    event: Event,
    db: Session = Depends(get_db),
) -> list[EstimationTaskInfo] | ErrorResponse:
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        tasks = (
            db.query(Task)
            .filter(Task.action == "estimation", Task.owner == owner)
            .order_by(Task.created_at)
            .all()
        )
        return [create_estimation_task_info(task) for task in tasks]
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.post(
    "/tasks/estimation",
    status_code=status.HTTP_201_CREATED,
    response_model=SubmitTaskResponse,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def submit_estimation_tasks(
    event: Event,
    request: EstimationTaskDef,
    db: Session = Depends(get_db),
) -> SubmitTaskResponse | ErrorResponse:
    try:
        device_info = db.get(Device, request.device)  # type: ignore
        if device_info is None:
            return BadRequestResponse(detail="device not found")
        owner = event.state.owner

        logger.info("invoked!", extra={"owner": owner})

        if device_info.status != "AVAILABLE":
            return BadRequestResponse(f"device {device_info.id} is not available")

        # NOTE: method and operator is needed for estimation task
        method = request.method

        if method not in ["state_vector", "sampling"]:
            return BadRequestResponse(
                detail="method should be either 'state_vector' or 'sampling'"
            )
        if request.method == "state_vector":
            if device_info.device_type != "simulator":
                return BadRequestResponse(
                    detail="state_vector method is valid only for simulator devices"
                )
            if request.nShots is not None:
                return BadRequestResponse(
                    detail="nShots is not valid for state_vector method"
                )
            shots = None
        else:  # sampling
            if request.nShots is None:
                return BadRequestResponse(
                    detail="nShots is mandatory for sampling method"
                )
            shots = request.nShots

        # operator is mandatory for estimation task
        operator = serialize_operator(request.operator)
        if isinstance(operator, BadRequestResponse):
            return operator
        # name is optional
        name = validate_name(request)
        code = request.code

        # NOTE:omit query from user_limits table logic

        resource = get_resources(request, device_info)
        if isinstance(resource, BadRequestResponse):
            return resource
        else:
            n_qubits, n_nodes = resource

        # qubit allocation is valid only for QPU devices
        qubit_allocation = validate_qubit_allocation(request, device_info)
        if isinstance(qubit_allocation, BadRequestResponse):
            return qubit_allocation

        # skip transpilation is False by default
        skip_transpilation = validate_skip_transpilation(request)
        if isinstance(skip_transpilation, BadRequestResponse):
            return skip_transpilation

        # seed transpilation is valid only for transpilation enabled tasks
        seed_transpilation = validate_seed_transpilation(request)
        if isinstance(seed_transpilation, BadRequestResponse):
            return seed_transpilation

        # seed simulation is valid only for simulator devices
        seed_simulation = validate_seed_simulation(request, device_info)
        if isinstance(seed_simulation, BadRequestResponse):
            return seed_simulation

        # ro error mitigation is valid only for QPU devices
        ro_error_mitigation = validate_ro_error_mitigation(request, device_info)
        if isinstance(ro_error_mitigation, BadRequestResponse):
            return ro_error_mitigation

        # n per node is valid only for simulator devices
        n_per_node = validate_n_per_node(request, device_info)
        if isinstance(n_per_node, BadRequestResponse):
            return n_per_node

        # simulation opt is valid only for simulator devices
        simulation_opt = validate_simulation_opt(request, device_info)
        if isinstance(simulation_opt, BadRequestResponse):
            return simulation_opt

        # note is optional
        note = validate_note(request)

        task = Task(
            id=uuid.uuid4().bytes,
            owner=owner,
            name=name,
            device=request.device,
            n_nodes=n_nodes,
            n_qubits=n_qubits,
            code=code,
            action="estimation",
            method=method,  # estimation task is using method
            shots=shots,
            operator=operator,  # estimation task is using operator
            qubit_allocation=qubit_allocation,
            skip_transpilation=skip_transpilation,
            seed_transpilation=seed_transpilation,
            seed_simulation=seed_simulation,
            ro_error_mitigation=ro_error_mitigation,
            n_per_node=n_per_node,
            simulation_opt=simulation_opt,
            note=note,
            created_at=datetime.now(),
        )
        db.add(task)
        db.commit()

        task_get = db.get(Task, task.id)
        if task_get is None:
            return NotFoundErrorResponse(
                detail=f"the created task {task.id} is not found"
            )

        return SubmitTaskResponse(
            taskId=task.id,
            createdAt=task.created_at.astimezone(jst),
            status=task_get.status,
        )
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/tasks/estimation/{taskId}",
    response_model=EstimationTaskInfo,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_estimation_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> EstimationTaskInfo | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        task = (
            db.query(Task)
            .filter(
                Task.id == task_id, Task.owner == owner, Task.action == "estimation"
            )
            .first()
        )
        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")
        return create_estimation_task_info(task)
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.delete(
    "/tasks/estimation/{taskId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def delete_estimation_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) ->  None | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})
        task = db.get(Task, task_id)

        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")

        if (
            task.owner != owner
            or task.action != "estimation"
            or task.status not in ["COMPLETED", "FAILED", "CANCELLED"]
        ):
            return NotFoundErrorResponse(
                detail=f"{taskId} task is not in valid status for deletion (valid statuses for deletion: 'COMPLETED', 'FAILED' and 'CANCELLED')"
            )

        db.delete(task)
        db.commit()
        return
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))


@router.get(
    "/tasks/estimation/{taskId}/status",
    response_model=GetEstimationTaskStatusResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_estimation_task_status(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> GetEstimationTaskStatusResponse | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    owner = event.state.owner
    logger.info("invoked!", extra={"owner": owner})
    task = (
        db.query(Task.id, Task.status)
        .filter(
            Task.id == uuid.UUID(taskId).bytes,
            Task.action == "estimation",
            Task.owner == owner,
        )
        .first()
    )
    if task is None:
        return NotFoundErrorResponse(detail="task not found with the given id")
    return GetEstimationTaskStatusResponse(
        taskId=TaskId(uuid.UUID(taskId)), status=TaskStatus(root=task.status)
    )


@router.post(
    "/tasks/estimation/{taskId}/cancel",
    response_model=SuccessResponse,
    responses={400: {"model": Detail}, 404: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def cancel_estimation_task(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | ErrorResponse:
    try:
        TaskId(root=uuid.UUID(taskId))
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        task_id = uuid.UUID(taskId).bytes
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        task = db.get(Task, task_id)

        if task is None:
            return NotFoundErrorResponse(detail="task not found with the given id")
        if (
            task.owner != owner
            or task.action != "estimation"
            or task.status not in ["QUEUED_FETCHED", "QUEUED", "RUNNING"]
        ):
            return NotFoundErrorResponse(
                detail=f"{taskId} task is not in valid status for cancellation (valid statuses for cancellation: 'QUEUED_FETCHED', 'QUEUED' and 'RUNNING')"
            )
        if task.status == "QUEUED":
            logger.info("task is in QUEUED state, so it will be cancelled")
            result = Result(
                task_id=task_id, status="CANCELLED", reason="user cancelled"
            )
            db.add(result)
            db.commit()
        elif task.status in ["QUEUED_FETCHED", "RUNNING"]:
            logger.info(
                "task is in QUEUED_FETCHED or RUNNING state, so it will be marked as CANCELLING"
            )
            task.status = "CANCELLING"
            db.commit()
        return SuccessResponse(message="cancell request accepted")
    except Exception as e:
        logger.info(f"error: {str(e)}")
        return InternalServerErrorResponse(detail=str(e))
