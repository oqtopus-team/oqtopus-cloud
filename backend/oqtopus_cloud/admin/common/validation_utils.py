from sqlalchemy.orm import (
    Session,
)

from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser

LEN_VARCHAR = 255
FIELD_REQUIRED_MESSAGE = "{} is required."
FIELD_TOO_LONG_MESSAGE = (
    "The length of {} exceeds the limit. Please enter within {} characters"
)
ALREADY_EXISTS_MESSAGE = "{} is already registered."


class FormatError(Exception):
    """Custom exception for formatting errors"""

    pass


def is_unique_user_id(session: Session, entity: type[User], user_id: str) -> bool:
    return session.query(entity).filter_by(id=user_id).first() is None


def is_unique_email(
    session: Session, entity: type[WhitelistUser] | type[User], email: str
) -> bool:
    return session.query(entity).filter_by(email=email).first() is None
