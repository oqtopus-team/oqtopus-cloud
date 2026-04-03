from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy import select, asc, desc
from sqlalchemy.orm import (
    Session,
)

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
    Message,
)
from oqtopus_cloud.admin.schemas.success import SuccessResponse
from oqtopus_cloud.admin.schemas.whitelist_users import (
    ListWhitelistUserResponse,
    ListWhitelistUsersResponse,
    RegisterWhitelistUserRequest,
    RegisterWhitelistUsersRequest,
    WhitelistUsersDeleteRequest,
)
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.available_devices import (
    convert_available_devices_to_string,
    parse_available_devices_string,
)
from oqtopus_cloud.admin.common.validation_utils import (
    ALREADY_EXISTS_MESSAGE,
    FIELD_REQUIRED_MESSAGE,
    FIELD_TOO_LONG_MESSAGE,
    FormatError,
    LEN_VARCHAR,
    is_unique_email,
)

from . import LoggerRouteHandler

COLUMNS_POSSIBLE_TO_ORDER_BY_DICT = {
    "id": WhitelistUser.id,
    "group_id": WhitelistUser.group_id,
    "email": WhitelistUser.email,
    "display_name": WhitelistUser.display_name,
    "organization": WhitelistUser.organization,
    "is_signup_completed": WhitelistUser.is_signup_completed,
    "available_devices": WhitelistUser.available_devices,
}

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def validated_whitelist_user(
    db: Session, user: RegisterWhitelistUserRequest
) -> WhitelistUser:
    if not user.email:
        raise FormatError(FIELD_REQUIRED_MESSAGE.format("email address"))
    if not user.group_id:
        raise FormatError(FIELD_REQUIRED_MESSAGE.format("group_id"))
    if not user.available_devices:
        raise FormatError(FIELD_REQUIRED_MESSAGE.format("available_devices"))

    if len(str(user.email)) > LEN_VARCHAR:
        raise FormatError(FIELD_TOO_LONG_MESSAGE.format(user.email, LEN_VARCHAR))
    if len(str(user.group_id)) > LEN_VARCHAR:
        raise FormatError(FIELD_TOO_LONG_MESSAGE.format(user.group_id, LEN_VARCHAR))
    if user.display_name and len(str(user.display_name)) > LEN_VARCHAR:
        raise FormatError(FIELD_TOO_LONG_MESSAGE.format(user.display_name, LEN_VARCHAR))
    if user.organization and len(str(user.organization)) > LEN_VARCHAR:
        raise FormatError(FIELD_TOO_LONG_MESSAGE.format(user.organization, LEN_VARCHAR))

    if not is_unique_email(db, WhitelistUser, user.email):
        raise FormatError(ALREADY_EXISTS_MESSAGE.format(user.email))

    validated_user = {
        "email": str(user.email),
        "group_id": str(user.group_id),
        "display_name": str(user.display_name),
        "organization": str(user.organization),
        "available_devices": convert_available_devices_to_string(
            user.available_devices
        ),
    }

    return WhitelistUser(**validated_user)


@router.get(
    "/whitelist_users",
    response_model=ListWhitelistUsersResponse,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def get_whitelist_users(
    offset: Optional[int] = 0,
    limit: Optional[int] = 10,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    organization: Optional[str] = None,
    group_id: Optional[str] = None,
    sort: Optional[str] = None,
    db: Session = Depends(get_db),
) -> ListWhitelistUsersResponse | BadRequestErrorResponse | InternalServerErrorResponse:
    logger.info("invoked get_whitelist_user")
    try:
        # query
        stmt = select(WhitelistUser)
        if email:
            stmt = stmt.where(WhitelistUser.email.ilike(f"%{email}%"))
        if display_name:
            stmt = stmt.where(WhitelistUser.display_name.ilike(f"%{display_name}%"))
        if organization:
            stmt = stmt.where(WhitelistUser.organization == organization)
        if group_id:
            stmt = stmt.where(WhitelistUser.group_id == group_id)
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
                order_list.append(order(WhitelistUser.id))

            stmt = stmt.order_by(*order_list)

        # pageination
        stmt = stmt.offset(offset).limit(limit)
        query_result = db.execute(stmt)
        scalars = query_result.scalars().all()

        whitelist_users = [model_to_schema(user) for user in scalars]

        return ListWhitelistUsersResponse(users=whitelist_users)
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.post(
    "/whitelist_users",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    responses={400: {"model": Message}, 500: {"model": Message}},
)
@tracer.capture_method
def register_whitelist_user(
    users: RegisterWhitelistUsersRequest,
    db: Session = Depends(get_db),
) -> SuccessResponse | BadRequestErrorResponse | InternalServerErrorResponse:
    logger.info("invoked create_whitelist_user")
    valid_users_list = []
    try:
        users_list = users.users
        if users_list is None:
            logger.error("No users to register")
            return BadRequestErrorResponse(message="No users to register")
        valid_users_list = [
            validated_whitelist_user(db, one_user) for one_user in users_list
        ]
    except Exception as e:
        logger.exception(f"error: {str(e)}")
        return BadRequestErrorResponse(message=str(e))
    if not valid_users_list:
        logger.error("No valid user to register")
        return BadRequestErrorResponse(message="No valid user to register")
    try:
        for user in valid_users_list:
            new_whitelist_user = WhitelistUser(
                group_id=user.group_id,
                email=user.email,
                display_name=user.display_name,
                organization=user.organization,
                is_signup_completed=user.is_signup_completed,
                available_devices=user.available_devices,
            )
            db.add(new_whitelist_user)
            db.commit()
        return SuccessResponse(message="Successfully registered")
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


@router.delete(
    "/whitelist_users",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={500: {"model": Message}},
)
@tracer.capture_method
def delete_whitelist_user(
    user_emails: WhitelistUsersDeleteRequest,
    db: Session = Depends(get_db),
) -> None | InternalServerErrorResponse:
    logger.info("invoked delete whitelist_user")
    try:
        if user_emails.user_emails is None:
            logger.info("No users to delete")
            return None
        stmt = select(WhitelistUser).where(
            WhitelistUser.email.in_(user_emails.user_emails)
        )
        # delete from RDS
        users_to_delete = db.scalars(stmt)
        if not users_to_delete:
            logger.info("No users to delete")
            return None
        for user in users_to_delete:
            db.delete(user)
        db.commit()
        return None
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse(message="Internal Server Error")


def model_to_schema(model: WhitelistUser) -> ListWhitelistUserResponse:
    return ListWhitelistUserResponse(
        id=model.id,
        group_id=model.group_id,
        email=model.email,
        display_name=getattr(model, "display_name", None),
        organization=getattr(model, "organization", None),
        is_signup_completed=getattr(model, "is_signup_completed", None),
        available_devices=parse_available_devices_string(
            getattr(model, "available_devices", None)
        ),
    )
