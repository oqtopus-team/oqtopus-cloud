from typing import Optional

import boto3
from fastapi import APIRouter, Body, Depends, status
from fastapi import Request as Event
from sqlalchemy import select, asc, desc
from sqlalchemy.orm import Session

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
    Message,
    NotFoundErrorResponse,
)
from oqtopus_cloud.admin.schemas.users import (
    GetOneUserResponse,
    GetUsersResponse,
    UpdateUserStatusRequest,
    UserStatus,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.user import UserStatus as UserStatusSchema
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.available_devices import parse_available_devices_string

from . import LoggerRouteHandler

COLUMNS_POSSIBLE_TO_ORDER_BY_DICT = {
    "id": User.id,
    "email": User.email,
    "name": User.username,
    "organization": User.organization,
    "status": User.userstatus,
    "group_id": User.group_id,
    "available_devices": User.available_devices,
}

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/users",
    response_model=GetUsersResponse,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_users(
    offset: Optional[int] = 0,
    limit: Optional[int] = 10,
    email: Optional[str] = None,
    name: Optional[str] = None,
    organization: Optional[str] = None,
    group_id: Optional[str] = None,
    status: Optional[UserStatus] = None,
    sort: Optional[str] = None,
    db: Session = Depends(get_db),
) -> GetUsersResponse | BadRequestErrorResponse | InternalServerErrorResponse:
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
        if group_id:
            stmt = stmt.where(User.group_id == group_id)
        if status:
            status_num = enum_to_status(status)
            if status_num is None:
                logger.error(f"Invalid status: {status}")
                return BadRequestErrorResponse(message=f"Invalid status: {status}")
            stmt = stmt.where(User.userstatus == status_num)
        if sort:
            sort_parts = sort.split(",")
            if len(sort_parts) != 2:
                logger.error(f"Invalid sort parameter: {sort}")
                return BadRequestErrorResponse(
                    message=f"Invalid sort parameter: {sort}"
                )

            column_name, order = sort_parts
            if column_name not in COLUMNS_POSSIBLE_TO_ORDER_BY_DICT:
                logger.error(f"Invalid column name to sort: {column_name}")
                return BadRequestErrorResponse(
                    message=f"Invalid column name to sort: {column_name}"
                )

            match order:
                case "asc":
                    stmt = stmt.order_by(
                        asc(COLUMNS_POSSIBLE_TO_ORDER_BY_DICT[column_name])
                    )
                case "desc":
                    stmt = stmt.order_by(
                        desc(COLUMNS_POSSIBLE_TO_ORDER_BY_DICT[column_name])
                    )
                case _:
                    logger.error(f"Invalid order to sort: {order}")
                    return BadRequestErrorResponse(
                        message=f"Invalid order to sort: {order}"
                    )

        stmt = stmt.offset(offset).limit(limit)
        query_result = db.execute(stmt)
        scalars = query_result.scalars().all()
        users = [model_to_schema(user) for user in scalars]

        return GetUsersResponse(offset=str(offset), limit=str(limit), users=users)
    except Exception as e:
        tracer.put_annotation("db_error", str(e))
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.patch(
    "/users/{user_id}",
    response_model=GetOneUserResponse,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def update_user_status(
    user_id: int,
    status_update: UpdateUserStatusRequest = Body(..., description="new status"),
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    try:
        logger.info("invoked update userstatus")
        # search the user
        stmt = select(User).where(User.id == user_id)
        query = db.execute(stmt).scalars().first()
        if not query:
            logger.error(f"User not found: {user_id}")
            return NotFoundErrorResponse(message=f"User not found: {user_id}")
        query.userstatus = enum_to_status(status_update.status)

        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except Exception as e:
        tracer.put_annotation("db_error", str(e))
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message=str(e))


@router.delete(
    "/users/{user_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": Message},
        500: {"model": Message},
    },
)
@tracer.capture_method
def delete_user(
    event: Event,
    user_id: int,
    db: Session = Depends(get_db),
) -> None | NotFoundErrorResponse | InternalServerErrorResponse:
    user_pool_id = event.state.user_pool_id
    region = event.state.region
    client = boto3.client("cognito-idp", region_name=region)
    try:
        logger.info("invoked delete user")
        # query
        stmt = select(User).where(User.id == user_id)
        # pageination
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            logger.error(f"User not found: {user_id}")
            return NotFoundErrorResponse(message=f"User not found: {user_id}")
        # delete from RDS
        db.delete(query_result)
        db.commit()

        # delete from cognito
        client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=query_result.email,
        )

        return None
    except Exception as e:
        tracer.put_annotation("db_error", str(e))
        logger.exception(f"error: {str(e)}")
        return InternalServerErrorResponse(message="Internal Server Error")


def model_to_schema(model: User) -> GetOneUserResponse:
    status = status_to_enum(getattr(model, "userstatus", None))
    return GetOneUserResponse(
        id=model.id,
        email=getattr(model, "email", None),
        name=getattr(model, "username", None),
        organization=getattr(model, "organization", None),
        group_id=getattr(model, "group_id", None),
        status=status,
        available_devices=parse_available_devices_string(
            getattr(model, "available_devices", None)
        ),
    )


def status_to_enum(status: UserStatusSchema | None) -> UserStatus | None:
    if status == UserStatusSchema.approved:
        return UserStatus.approved
    elif status == UserStatusSchema.unapproved:
        return UserStatus.unapproved
    elif status == UserStatusSchema.suspended:
        return UserStatus.suspended
    else:
        return None


def enum_to_status(status: UserStatus | None) -> UserStatusSchema | None:
    if status == UserStatus.approved:
        return UserStatusSchema.approved
    elif status == UserStatus.unapproved:
        return UserStatusSchema.unapproved
    elif status == UserStatus.suspended:
        return UserStatusSchema.suspended
    else:
        return None
