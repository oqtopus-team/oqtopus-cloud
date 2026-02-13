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
from oqtopus_cloud.common.i18n import Messages
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser
from oqtopus_cloud.common.session import (
    get_db,
)
from oqtopus_cloud.common.available_devices import (
    convert_available_devices_to_string,
    parse_available_devices_string,
)
from oqtopus_cloud.admin.common.validation_utils import (
    FormatError,
    LEN_VARCHAR,
    is_unique_email,
)

from . import LoggerRouteHandler

COLUMNS_POSSIBLE_TO_ORDER_BY_DICT = {
    "id": WhitelistUser.id,
    "group_id": WhitelistUser.group_id,
    "email": WhitelistUser.email,
    "username": WhitelistUser.username,
    "organization": WhitelistUser.organization,
    "is_signup_completed": WhitelistUser.is_signup_completed,
    "available_devices": WhitelistUser.available_devices,
}

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def validated_whitelist_user(
    db: Session, user: RegisterWhitelistUserRequest
) -> WhitelistUser:
    if not user.email:
        raise FormatError(**Messages.FIELD_REQUIRED.format(field="email").to_dict())
    if not user.group_id:
        raise FormatError(**Messages.FIELD_REQUIRED.format(field="group_id").to_dict())
    if not user.available_devices:
        raise FormatError(
            **Messages.FIELD_REQUIRED.format(field="available_devices").to_dict()
        )

    if len(str(user.email)) > LEN_VARCHAR:
        raise FormatError(
            **Messages.FIELD_TOO_LONG.format(field="email", limit=LEN_VARCHAR).to_dict()
        )
    if len(str(user.group_id)) > LEN_VARCHAR:
        raise FormatError(
            **Messages.FIELD_TOO_LONG.format(
                field="group_id", limit=LEN_VARCHAR
            ).to_dict()
        )
    if user.username and len(str(user.username)) > LEN_VARCHAR:
        raise FormatError(
            **Messages.FIELD_TOO_LONG.format(
                field="username", limit=LEN_VARCHAR
            ).to_dict()
        )
    if user.organization and len(str(user.organization)) > LEN_VARCHAR:
        raise FormatError(
            **Messages.FIELD_TOO_LONG.format(
                field="organization", limit=LEN_VARCHAR
            ).to_dict()
        )

    if not is_unique_email(db, WhitelistUser, user.email):
        raise FormatError(
            **Messages.EMAIL_ALREADY_EXISTS.format(email=user.email).to_dict()
        )

    validated_user = {
        "email": str(user.email),
        "group_id": str(user.group_id),
        "username": str(user.username),
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
    username: Optional[str] = None,
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
        if username:
            stmt = stmt.where(WhitelistUser.username.ilike(f"%{username}%"))
        if organization:
            stmt = stmt.where(WhitelistUser.organization == organization)
        if group_id:
            stmt = stmt.where(WhitelistUser.group_id == group_id)
        if sort:
            sort_parts = sort.split(",")
            if len(sort_parts) != 2:
                message = Messages.INVALID_SORT_PARAMETER.format(sort=sort)
                logger.error(message.message)
                return BadRequestErrorResponse(**message.to_dict())

            column_name, order_str = sort_parts
            if column_name not in COLUMNS_POSSIBLE_TO_ORDER_BY_DICT:
                message = Messages.INVALID_SORT_COLUMN.format(column=column_name)
                logger.error(message.message)
                return BadRequestErrorResponse(**message.to_dict())

            match order_str:
                case "asc":
                    order = asc
                case "desc":
                    order = desc
                case _:
                    message = Messages.INVALID_SORT_ORDER.format(order=order_str)
                    logger.error(message.message)
                    return BadRequestErrorResponse(**message.to_dict())

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
        return InternalServerErrorResponse()


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
            message = Messages.NO_USERS_TO_REGISTER.format()
            logger.error(message.message)
            return BadRequestErrorResponse(**message.to_dict())
        valid_users_list = [
            validated_whitelist_user(db, one_user) for one_user in users_list
        ]
    except FormatError as e:
        logger.exception(e.message)
        return BadRequestErrorResponse(
            message=e.message,
            message_code=e.message_code,
            message_params=e.message_params,
        )
    if not valid_users_list:
        message = Messages.NO_VALID_USER_TO_REGISTER.format()
        logger.error(message.message)
        return BadRequestErrorResponse(**message.to_dict())
    try:
        for user in valid_users_list:
            new_whitelist_user = WhitelistUser(
                group_id=user.group_id,
                email=user.email,
                username=user.username,
                organization=user.organization,
                is_signup_completed=user.is_signup_completed,
                available_devices=user.available_devices,
            )
            db.add(new_whitelist_user)
            db.commit()
        return SuccessResponse(**Messages.WHITELIST_USER_REGISTERED.format().to_dict())
    except Exception as e:
        tracer.put_annotation("error", str(e))
        logger.exception(f"Internal Server Error: {e}")
        return InternalServerErrorResponse()


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
        return InternalServerErrorResponse()


def model_to_schema(model: WhitelistUser) -> ListWhitelistUserResponse:
    return ListWhitelistUserResponse(
        id=model.id,
        group_id=model.group_id,
        email=model.email,
        username=getattr(model, "username", None),
        organization=getattr(model, "organization", None),
        is_signup_completed=getattr(model, "is_signup_completed", None),
        available_devices=parse_available_devices_string(
            getattr(model, "available_devices", None)
        ),
    )
