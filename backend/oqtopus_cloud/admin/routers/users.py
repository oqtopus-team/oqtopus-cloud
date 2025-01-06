from typing import Any, Optional

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.users import (
    GetUsersResponse,
)
from oqtopus_cloud.admin.schemas.user import (
    GetOneUserResponse,
)
from oqtopus_cloud.admin.schemas.user import (
    UserUpdateStatusRequest,
)
from oqtopus_cloud.admin.schemas.success import SuccessResponse
from oqtopus_cloud.admin.schemas.error import (
    NotFoundError,
    InternalServerError,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/users",
    response_model=GetUsersResponse,
    responses={500: {"model": InternalServerError}},
)
@tracer.capture_method
def get_users(
    offset: Optional[str] = "0",
    limit: Optional[str] = "10",
    email: Optional[str] = None,
    name: Optional[str] = None,
    organization: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
) -> GetUsersResponse | InternalServerError:
    try:
        logger.info("invoked list_users")
        # query
        stmt = select(User)
        if email:
            stmt = stmt.where(User.email.ilike(f"%{email}%"))
        if name:
            stmt = stmt.where(User.username.ilike(f"%{name}%"))
        if organization:
            stmt = stmt.where(User.organization == organization)
        if status:
            stmt = stmt.where(User.userstatus == status)
        # pageination
        stmt = stmt.offset(int(offset)).limit(int(limit))
        query_result = db.execute(stmt)
        query_result = query_result.scalars().all()
        users = [model_to_schema(user) for user in query_result]

        return GetUsersResponse(Offset=offset, Limit=limit, users=users)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerError(detail=str(e))


@router.put(
    "/users/{user_id}",
    response_model=GetOneUserResponse,
    responses={404: {"model": NotFoundError}, 500: {"model": InternalServerError}},
)
@tracer.capture_method
def update_user_status(
    user_id: str,
    status_update: UserUpdateStatusRequest = Body(..., description="new status"),
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundError | InternalServerError:
    try:
        logger.info("invoked update userstatus")
        # query
        stmt = select(User).where(User.id == user_id)
        query = db.execute(stmt).scalars().first()
        # pageination
        if not query:
            raise NotFoundError(status_code=404, detail="User not found")
        query.userstatus = status_update.status

        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except SQLAlchemyError as e:
        tracer.put_annotation("db_error", str(e))
        return InternalServerError(status_code=500, detail="Internal Server Error")


@router.delete(
    "/users/{user_id}",
    response_model=SuccessResponse,
    responses={404: {"model": NotFoundError}, 500: {"model": InternalServerError}},
)
@tracer.capture_method
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | NotFoundError | InternalServerError:
    try:
        logger.info("invoked delete user")
        # query
        stmt = select(User).where(User.id == user_id)
        # pageination
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            return NotFoundError(status_code=404, detail="User not found")

        db.delete(query_result)
        db.commit()

        return SuccessResponse(message="User deleted successfully")
    except SQLAlchemyError as e:
        tracer.put_annotation("db_error", str(e))
        return InternalServerError(status_code=500, detail="Internal Server Error")


def model_to_schema(model: User) -> GetOneUserResponse:
    return GetOneUserResponse(
        id=str(getattr(model, "id", None)),
        email=getattr(model, "email", None),
        name=getattr(model, "username", None),
        organization=getattr(model, "organization", None),
        status=getattr(model, "userstatus", None),
        require_mfa_reset=getattr(model, "require_mfa_reset", None),
    )
