import uuid
from ast import literal_eval

from fastapi import APIRouter, Depends
from fastapi import Request as Event
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from oqtopus_cloud.common.models.result import Result as ResultModel
from oqtopus_cloud.common.models.task import Task
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.user.conf import logger, tracer
from oqtopus_cloud.user.schemas.errors import (
    BadRequestResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.user.schemas.results import (
    EstimationResultDef,
    ResultStatus,
    SamplingResultDef,
)
from oqtopus_cloud.user.schemas.tasks import TaskId

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)
# jst = ZoneInfo("Asia/Tokyo")
tz = ZoneInfo("UTC")


def create_sampling_result(result_model: ResultModel) -> SamplingResultDef:
    print(result_model.task_id)
    print(result_model.status)
    print(result_model.result)
    print(result_model.reason)
    print(result_model.transpiled_code)
    print(result_model.qubit_allocation)
    if result_model.status == "SUCCESS":
        result = literal_eval(result_model.result)
        reason = None
    else:
        result = None
        reason = result_model.reason
    if result_model.qubit_allocation is not None:
        qubit_allocation = literal_eval(result_model.qubit_allocation)
    else:
        qubit_allocation = None
    return SamplingResultDef(
        taskId=TaskId(result_model.task_id),
        status=ResultStatus(root=result_model.status),  # type: ignore
        result=result,
        reason=reason,
        transpiledCode=result_model.transpiled_code,
        qubitAllocation=qubit_allocation,
    )


def create_estimation_result(result_model: ResultModel) -> EstimationResultDef:
    print(result_model.task_id)
    print(result_model.status)
    print(result_model.result)
    print(result_model.reason)
    print(result_model.transpiled_code)
    print(result_model.qubit_allocation)
    if result_model.status == "SUCCESS":
        result = literal_eval(result_model.result)
        reason = None
    else:
        result = None
        reason = result_model.reason
    if result_model.qubit_allocation is not None:
        qubit_allocation = literal_eval(result_model.qubit_allocation)
    else:
        qubit_allocation = None
    return EstimationResultDef(
        taskId=TaskId(result_model.task_id),
        status=ResultStatus(root=result_model.status),  # type: ignore
        result=result,
        reason=reason,
        transpiledCode=result_model.transpiled_code,
        qubitAllocation=qubit_allocation,
    )


@router.get(
    "/results/sampling/{taskId}",
    response_model=SamplingResultDef,
    responses={
        404: {"model": Detail},
        409: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def get_sampling_result(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> SamplingResultDef | ErrorResponse:
    logger.info("invoked get_tasks")
    try:
        task_id = uuid.UUID(taskId).bytes
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        stmt = (
            select(ResultModel)
            .join(Task, ResultModel.task_id == Task.id)
            .filter(
                Task.owner == owner,
                ResultModel.task_id == task_id,
                Task.action == "sampling",
            )
        )
        result = db.scalars(stmt).first()

        if result is None:
            return NotFoundErrorResponse("result not found")
        return create_sampling_result(result)
    except Exception as e:
        return InternalServerErrorResponse(str(e))


@router.get(
    "/results/estimation/{taskId}",
    response_model=EstimationResultDef,
    responses={
        404: {"model": Detail},
        409: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def get_estimation_result(
    event: Event,
    taskId: str,
    db: Session = Depends(get_db),
) -> EstimationResultDef | ErrorResponse:
    logger.info("invoked get_tasks")
    try:
        task_id = uuid.UUID(taskId).bytes
    except ValidationError:
        logger.info(f"invalid task id: {taskId}")
        return BadRequestResponse(detail="invalid task id")
    try:
        owner = event.state.owner
        logger.info("invoked!", extra={"owner": owner})

        stmt = (
            select(ResultModel)
            .join(Task, ResultModel.task_id == Task.id)
            .filter(
                Task.owner == owner,
                ResultModel.task_id == task_id,
                Task.action == "estimation",
            )
        )
        result = db.scalars(stmt).first()

        if result is None:
            return NotFoundErrorResponse("result not found")
        return create_estimation_result(result)
    except Exception as e:
        return InternalServerErrorResponse(str(e))
