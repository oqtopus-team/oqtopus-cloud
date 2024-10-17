import uuid
from ast import literal_eval
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from oqtopus_cloud.common.models.task import Task
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.provider.schemas.tasks import (
    Action,
    EstimationAction,
    SamplingAction,
    TaskId,
    TaskInfo,
    TaskStatusUpdate,
    TaskStatusUpdateResponse,
    UnfetchedTasksResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")


def create_task_info(task: Task, status=None) -> TaskInfo:
    if status is None:
        status = task.status
    return TaskInfo(
        taskId=TaskId(task.id),
        code=task.code,
        device=task.device,
        nQubits=task.n_qubits,
        nNodes=task.n_nodes,
        action=Action(recreate_task_action(task)),
        qubitAllocation=task.qubit_allocation,
        skipTranspilation=task.skip_transpilation,
        seedTranspilation=task.seed_transpilation,
        seedSimulation=task.seed_simulation,
        roErrorMitigation=task.ro_error_mitigation,
        nPerNode=task.n_per_node,
        simulationOpt=task.simulation_opt,
        status=status,  # type: ignore
        createdAt=task.created_at.astimezone(jst),
    )


@router.get(
    "/tasks",
    response_model=list[TaskInfo],
)
@tracer.capture_method
def get_tasks(
    deviceId: str,
    status: Optional[str] = None,
    maxResults: Optional[int] = None,
    timestamp: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[TaskInfo]:
    logger.info("invoked get_tasks")
    stmt = select(Task).filter(Task.device == deviceId)
    if status is not None:
        stmt = stmt.filter(Task.status == status)
    if timestamp is not None:
        time = datetime.fromisoformat(timestamp).astimezone(jst)
        stmt = stmt.filter(Task.created_at > time)
    if maxResults is not None:
        stmt = stmt.limit(maxResults)

    tasks = db.scalars(stmt).all()
    return [create_task_info(task, status=None) for task in tasks]


@router.get(
    "/tasks/unfetched",
    response_model=UnfetchedTasksResponse,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_unfetched_tasks(
    deviceId: str,
    status: str,
    maxResults: Optional[int] = None,
    db: Session = Depends(get_db),
) -> UnfetchedTasksResponse | ErrorResponse:
    logger.info("invoked get_task")
    try:
        if status not in ["QUEUED", "CANCELLING"]:
            return BadRequestResponse("Invalid status")
        if status == "QUEUED":
            stmt = (
                select(Task)
                .where(Task.device == deviceId, Task.status == "QUEUED")
                .order_by(Task.created_at)
            )
            update_status = "QUEUED_FETCHED"
        else:
            stmt = select(Task).where(Task.device == deviceId).order_by(Task.created_at)
            update_status = "CANCELLING_FETCHED"

        if maxResults is not None:
            stmt = stmt.limit(maxResults)

        tasks = db.scalars(stmt).all()
        if len(tasks) != 0:
            for task in tasks:
                task.status = update_status  # type: ignore
            db.commit()
        if status == "QUEUED":
            task_info = [create_task_info(task, status=update_status) for task in tasks]
            return UnfetchedTasksResponse(root=task_info)  # type: ignore
        else:
            task_ids = [TaskId(task.id) for task in tasks]
            return UnfetchedTasksResponse(root=task_ids)  # type: ignore
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.get(
    "/tasks/{taskId}",
    response_model=TaskInfo,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def get_task(
    taskId: str,
    db: Session = Depends(get_db),
) -> TaskInfo | ErrorResponse:
    logger.info("invoked get_task")
    try:
        id = uuid.UUID(taskId).bytes
    except Exception:
        return BadRequestResponse("Invalid taskId")
    try:
        task = db.get(Task, id)
        if task is None:
            return NotFoundErrorResponse("Task not found")
        return create_task_info(task)
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


@router.patch(
    "/tasks/{taskId}",
    response_model=TaskStatusUpdateResponse,
    responses={404: {"model": Detail}, 400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def update_task(
    taskId: str,
    request: TaskStatusUpdate,
    db: Session = Depends(get_db),
) -> TaskStatusUpdateResponse | ErrorResponse:
    logger.info("invoked get_task")
    try:
        id = uuid.UUID(taskId).bytes
    except Exception:
        return BadRequestResponse("Invalid taskId")
    try:
        task = db.scalars(select(Task).filter(Task.id == id)).first()
        if task is None:
            return NotFoundErrorResponse("Task not found")
        if request.status is not None:
            task.status = request.status  # type: ignore
        db.commit()
        return TaskStatusUpdateResponse(message="Task status updated")
    except Exception as e:
        return InternalServerErrorResponse(f"Error: {str(e)}")


def recreate_task_action(task: Task):
    action_name = task.action
    action_shots = task.shots
    action_method = task.method
    action_operator = task.operator
    if action_name == "sampling":
        return SamplingAction(
            name=action_name,
            nShots=action_shots,
        )
    else:
        # :TODO: remove Enum
        return EstimationAction(
            name=action_name,  # type: ignore
            method=action_method,  # type: ignore
            nShots=action_shots,
            operator=literal_eval(action_operator),
        )
