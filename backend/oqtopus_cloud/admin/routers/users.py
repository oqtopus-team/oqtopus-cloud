# import os
from typing import Optional

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
import boto3
from fastapi import Request as Event

# from database import get_db_client

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
from oqtopus_cloud.admin.schemas.errors import (
    Detail,
    NotFoundErrorResponse,
    InternalServerErrorResponse,
)

from . import LoggerRouteHandler

utc = ZoneInfo("UTC")
jst = ZoneInfo("Asia/Tokyo")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


@router.get(
    "/users",
    response_model=GetUsersResponse,
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_users(
    offset: Optional[int] = 0,
    limit: Optional[int] = 10,
    email: Optional[str] = None,
    name: Optional[str] = None,
    organization: Optional[str] = None,
    group_id: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
) -> GetUsersResponse | InternalServerErrorResponse:
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
            stmt = stmt.where(User.userstatus == status)
        # pageination
        stmt = stmt.offset(offset).limit(limit)
        query_result = db.execute(stmt)
        scalars = query_result.scalars().all()
        users = [model_to_schema(user) for user in scalars]

        return GetUsersResponse(Offset=str(offset), Limit=str(limit), users=users)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))


@router.put(
    "/users/{user_id}",
    response_model=GetOneUserResponse,
    responses={
        404: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def update_user_status(
    user_id: str,
    status_update: UserUpdateStatusRequest = Body(..., description="new status"),
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    try:
        logger.info("invoked update userstatus")
        # query
        stmt = select(User).where(User.id == user_id)
        query = db.execute(stmt).scalars().first()
        if not query:
            return NotFoundErrorResponse(message="User not found")
        # state not updated
        if status_update.status is None:
            return model_to_schema(query)
        query.userstatus = int(status_update.status)

        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except SQLAlchemyError as e:
        tracer.put_annotation("db_error", str(e))
        return InternalServerErrorResponse(message="Internal Server Error")


@router.put(
    "/users/{user_id}/mfa_reset",
    response_model=GetOneUserResponse,
    responses={
        404: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def reset_user_mfa(
    event: Event,
    user_id: str,
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    owner = event.state.owner
    user_pool_id = event.state.user_pool_id
    region = event.state.region
    client = boto3.client("cognito-idp", region_name=region)
    logger.info(f"owner: {owner}, user_pool_id: {user_pool_id}")
    try:
        logger.info("invoked mfa_reset")
        # query
        stmt = select(User).where(User.id == user_id)
        query = db.execute(stmt).scalars().first()
        if not query:
            return NotFoundErrorResponse(message="User not found")

        response = client.admin_set_user_mfa_preference(
            # SMS MFA setting enabled
            SMSMfaSettings={"Enabled": True, "PreferredMfa": True},
            # TOTP MFA setting disabled
            SoftwareTokenMfaSettings={"Enabled": False, "PreferredMfa": False},
            Username=owner,
            UserPoolId=user_pool_id,
        )
        logger.info(f"mfa reset response: {response}")
        # change MFA reset status
        query.require_mfa_reset = False
        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except SQLAlchemyError as e:
        tracer.put_annotation("db_error", str(e))
        return InternalServerErrorResponse(message="Internal Server Error")


# TODO : delete from cognito
@router.delete(
    "/users/{user_id}",
    response_model=SuccessResponse,
    responses={
        404: {"model": Detail},
        500: {"model": Detail},
    },
)
@tracer.capture_method
def delete_user(
    event: Event,
    user_id: str,
    db: Session = Depends(get_db),
) -> SuccessResponse | NotFoundErrorResponse | InternalServerErrorResponse:
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
            return NotFoundErrorResponse(message="User not found")
        # delete from RDS
        db.delete(query_result)
        db.commit()

        # delete from cognito
        response = client.admin_delete_user(
            UserPoolId=user_pool_id,
            Username=query_result.email,
        )

        return SuccessResponse(message="User deleted successfully")
    except SQLAlchemyError as e:
        tracer.put_annotation("db_error", str(e))
        return InternalServerErrorResponse(message="Internal Server Error")


def model_to_schema(model: User) -> GetOneUserResponse:
    return GetOneUserResponse(
        id=str(getattr(model, "id", None)),
        email=getattr(model, "email", None),
        name=getattr(model, "username", None),
        organization=getattr(model, "organization", None),
        group_id=getattr(model, "group_id", None),
        status=getattr(model, "userstatus", None),
        require_mfa_reset=getattr(model, "require_mfa_reset", None),
    )
