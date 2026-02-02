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
    UpdateUserRequest,
    UserStatus,
)
from oqtopus_cloud.admin.common.validation_utils import (
    EMAIL_ALREADY_EXISTS_MESSAGE,
    FIELD_TOO_LONG_MESSAGE,
    LEN_VARCHAR,
    is_unique_email,
    FormatError,
)
from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.user import UserStatus as UserStatusSchema
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.available_devices import (
    convert_available_devices_to_string,
    parse_available_devices_string,
)

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

            column_name, order_str = sort_parts
            if column_name not in COLUMNS_POSSIBLE_TO_ORDER_BY_DICT:
                logger.error(f"Invalid column name to sort: {column_name}")
                return BadRequestErrorResponse(
                    message=f"Invalid column name to sort: {column_name}"
                )

            match order_str:
                case "asc":
                    order = asc
                case "desc":
                    order = desc
                case _:
                    logger.error(f"Invalid order to sort: {order_str}")
                    return BadRequestErrorResponse(
                        message=f"Invalid order to sort: {order_str}"
                    )

            order_list = [order(COLUMNS_POSSIBLE_TO_ORDER_BY_DICT[column_name])]
            if column_name != "id":
                order_list.append(order(User.id))

            stmt = stmt.order_by(*order_list)

        stmt = stmt.offset(offset).limit(limit)
        query_result = db.execute(stmt)
        scalars = query_result.scalars().all()
        users = [model_to_schema(user) for user in scalars]

        return GetUsersResponse(offset=str(offset), limit=str(limit), users=users)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


@router.get(
    "/users/{user_id}",
    response_model=GetOneUserResponse,
    responses={404: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
) -> GetOneUserResponse | NotFoundErrorResponse | InternalServerErrorResponse:
    logger.info("invoked get user")
    try:
        user = db.scalars(select(User).where(User.id == user_id)).first()

        if user is None:
            message = f"user_id={user_id} is not found."
            logger.info(message)
            return NotFoundErrorResponse(message=message)

        return model_to_schema(user)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


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
    update_user_request: UpdateUserRequest = Body(..., description="new status"),
    db: Session = Depends(get_db),
) -> (
    GetOneUserResponse
    | NotFoundErrorResponse
    | BadRequestErrorResponse
    | InternalServerErrorResponse
):
    try:
        logger.info("invoked update user")
        # search the user
        stmt = select(User).where(User.id == user_id)
        query = db.execute(stmt).scalars().first()
        if not query:
            logger.error(f"User not found: {user_id}")
            return NotFoundErrorResponse(message=f"User not found: {user_id}")

        if update_user_request.email:
            if len(update_user_request.email) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(
                        update_user_request.email, LEN_VARCHAR
                    )
                )
            if not is_unique_email(db, User, update_user_request.email):
                raise FormatError(
                    EMAIL_ALREADY_EXISTS_MESSAGE.format(update_user_request.email)
                )
            query.email = update_user_request.email

        if update_user_request.name:
            if len(update_user_request.name) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(update_user_request.name, LEN_VARCHAR)
                )
            query.username = update_user_request.name

        if update_user_request.organization:
            if len(update_user_request.organization) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(
                        update_user_request.organization, LEN_VARCHAR
                    )
                )
            query.organization = update_user_request.organization

        if update_user_request.group_id:
            if len(update_user_request.group_id) > LEN_VARCHAR:
                raise FormatError(
                    FIELD_TOO_LONG_MESSAGE.format(
                        update_user_request.group_id, LEN_VARCHAR
                    )
                )
            query.group_id = update_user_request.group_id

        if update_user_request.status:
            query.userstatus = enum_to_status(update_user_request.status)

        available_devices = convert_available_devices_to_string(
            update_user_request.available_devices
        )
        if available_devices is not None:
            query.available_devices = available_devices

        # commit the transaction
        db.commit()
        # refresh the object to get the updated value
        db.refresh(query)
        user = model_to_schema(query)

        return user
    except FormatError as e:
        logger.exception(f"error: {str(e)}")
        return BadRequestErrorResponse(message=str(e))
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


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
        # pagination
        query_result = db.execute(stmt).scalars().first()
        if not query_result:
            logger.error(f"User not found: {user_id}")
            return NotFoundErrorResponse(message=f"User not found: {user_id}")
        # check if the user is in whitelist_users
        stmt_whitelist = select(WhitelistUser).where(
            WhitelistUser.email == query_result.email
        )
        query_result_whitelist = db.execute(stmt_whitelist).scalars().first()
        if query_result_whitelist:
            query_result_whitelist.is_signup_completed = False
        else:
            logger.warning(
                f"User {query_result.email} is not in whitelist_users. Skipping the change of is_signup_completed."
            )
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
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


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
