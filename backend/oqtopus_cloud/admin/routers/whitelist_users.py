import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
)
from zoneinfo import ZoneInfo

from oqtopus_cloud.admin.conf import logger, tracer
from oqtopus_cloud.admin.schemas.errors import (
    BadRequestErrorResponse,
    Detail,
    InternalServerErrorResponse,
)
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

from . import LoggerRouteHandler

LEN_VARCHAR = 255

jst = ZoneInfo("Asia/Tokyo")
utc = ZoneInfo("UTC")

router: APIRouter = APIRouter(route_class=LoggerRouteHandler)


def is_unique_email(session, email):
    return session.query(WhitelistUser).filter_by(email=email).first() is None


def validated_whitelist_user(
    db: Session, user: RegisterWhitelistUserRequest
) -> WhitelistUser:
    required_msg = "{} is required."
    too_long_msg = (
        "The length of {} exceeds the limit. Please enter within {} characters."
    )
    if not user.email:
        raise Exception(required_msg.format("email address"))
    if not user.group_id:
        raise Exception(required_msg.format("group_id"))

    if len(str(user.email)) > LEN_VARCHAR:
        raise Exception(too_long_msg.format(user.email, LEN_VARCHAR))
    if len(str(user.group_id)) > LEN_VARCHAR:
        raise Exception(too_long_msg.format(user.group_id, LEN_VARCHAR))
    if user.username and len(str(user.username)) > LEN_VARCHAR:
        raise Exception(too_long_msg.format(user.username, LEN_VARCHAR))
    if user.organization and len(str(user.organization)) > LEN_VARCHAR:
        raise Exception(too_long_msg.format(user.organization, LEN_VARCHAR))

    if not is_unique_email(db, user.email):
        raise Exception(f"{user.email} is already registered.")

    validated_user = {
        "email": str(user.email),
        "group_id": str(user.group_id),
        "username": str(user.username),
        "organization": str(user.organization),
    }

    return WhitelistUser(**validated_user)


@router.get(
    "/whitelist_users",
    response_model=ListWhitelistUsersResponse,
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def get_whitelist_users(
    offset: Optional[int] = 0,
    limit: Optional[int] = 10,
    email: Optional[str] = None,
    username: Optional[str] = None,
    organization: Optional[str] = None,
    group_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> ListWhitelistUsersResponse | InternalServerErrorResponse:
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
        # pageination
        stmt = stmt.offset(offset).limit(limit)
        query_result = db.execute(stmt)
        scalars = query_result.scalars().all()

        whitelist_users = [model_to_schema(user) for user in scalars]

        return ListWhitelistUsersResponse(users=whitelist_users)
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))


@router.post(
    "/whitelist_users",
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={400: {"model": Detail}, 500: {"model": Detail}},
)
@tracer.capture_method
def register_whitelist_user(
    users: RegisterWhitelistUsersRequest,
    db: Session = Depends(get_db),
) -> None | BadRequestErrorResponse | InternalServerErrorResponse:
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
        logger.error(f"error: {str(e)}", stack_info=True)
        return BadRequestErrorResponse(message=str(e))
    if not valid_users_list:
        logger.error("No valid user to register")
        return BadRequestErrorResponse(message="No valid user to register")
    try:
        for user in valid_users_list:
            new_whitelist_user = WhitelistUser(
                group_id=user.group_id,
                email=user.email,
                username=user.username,
                organization=user.organization,
                is_signup_completed=user.is_signup_completed,
                created_at=datetime.datetime.now(utc),
                updated_at=datetime.datetime.now(utc),
            )
            db.add(new_whitelist_user)
            db.commit()
        return None
    except Exception as e:
        logger.error(f"error: {str(e)}", stack_info=True)
        return InternalServerErrorResponse(message=str(e))


@router.delete(
    "/whitelist_users",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={500: {"model": Detail}},
)
@tracer.capture_method
def delete_whitelist_user(
    user_emails: WhitelistUsersDeleteRequest,
    db: Session = Depends(get_db),
) -> None | InternalServerErrorResponse:
    logger.info("invoked delete whitelist_user")
    try:
        if user_emails.user_emails is None:
            return None
        stmt = select(WhitelistUser).where(
            WhitelistUser.email.in_(user_emails.user_emails)
        )
        # delete from RDS
        users_to_delete = db.scalars(stmt)
        if not users_to_delete:
            return None
        for user in users_to_delete:
            db.delete(user)
        db.commit()
        return None
    except Exception as e:
        return InternalServerErrorResponse(message=str(e))


def model_to_schema(model: WhitelistUser) -> ListWhitelistUserResponse:
    return ListWhitelistUserResponse(
        id=model.id,
        group_id=model.group_id,
        email=model.email,
        username=getattr(model, "username", None),
        organization=getattr(model, "organization", None),
        is_signup_completed=getattr(model, "is_signup_completed", None),
    )
