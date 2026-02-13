from sqlalchemy.orm import (
    Session,
)

from oqtopus_cloud.common.models.user import User
from oqtopus_cloud.common.models.whitelist_user import WhitelistUser

LEN_VARCHAR = 255


class FormatError(Exception):
    """Custom exception for formatting errors"""

    def __init__(self, message_code: str, message_params: dict[str, str], message: str):
        super().__init__(message_code, message_params, message)
        self.message_code = message_code
        self.message_params = message_params
        self.message = message


def is_unique_email(
    session: Session, entity: type[WhitelistUser] | type[User], email: str
) -> bool:
    return session.query(entity).filter_by(email=email).first() is None
