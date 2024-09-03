from fastapi import APIRouter, Depends
from oqtopus_cloud.common.models.result import Result as ResultModel
from oqtopus_cloud.common.models.task import Task
from oqtopus_cloud.common.session import get_db
from oqtopus_cloud.provider.conf import logger, tracer
from oqtopus_cloud.provider.schemas.errors import (
    ConflictErrorResponse,
    Detail,
    ErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from oqtopus_cloud.provider.schemas.results import (
    CreateResultResponse,
    ResultDef,
)
from sqlalchemy.orm import Session

from . import LoggerRouteHandler

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.post(
    "/internal/results",
    response_model=CreateResultResponse,
    responses={
        404: {"model": Detail},
        409: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def create_result(
    request: ResultDef,
    db: Session = Depends(get_db),
) -> CreateResultResponse | ErrorResponse:
    logger.info("invoked get_tasks")
    task_id = request.taskId.root.bytes
    if request.qubitAllocation is None:
        qubitAllocation = None
    try:
        result = db.get(ResultModel, task_id)
        if result is not None:
            return ConflictErrorResponse("Result already exists")
        task = db.get(Task, task_id)
        if task is None:
            return NotFoundErrorResponse("Task not found")
        new_result = ResultModel(
            task_id=task_id,
            status=request.status.root,
            result=request.result.model_dump_json(),
            reason=request.reason,
            transpiled_code=request.transpiledCode,
            qubit_allocation=qubitAllocation,
        )
        db.add(new_result)
        db.commit()
        return CreateResultResponse(message="success")
    except Exception as e:
        return InternalServerErrorResponse(str(e))
