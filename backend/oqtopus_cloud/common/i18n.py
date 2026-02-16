from enum import Enum
from dataclasses import dataclass, asdict


@dataclass
class MessageTemplate:
    message_code: str
    message_params: list[str]
    message_template: str


@dataclass
class Message:
    message_code: str
    message_params: dict[str, str]
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class Messages(Enum):
    ANNOUNCEMENT_NOT_FOUND = MessageTemplate(
        message_code="ANNOUNCEMENT_NOT_FOUND",
        message_params=["id"],
        message_template="announcement_id={id} is not found.",
    )

    ANNOUNCEMENT_REGISTERED = MessageTemplate(
        message_code="ANNOUNCEMENT_REGISTERED",
        message_params=[],
        message_template="Announcement registered successfully",
    )

    ANNOUNCEMENT_UPDATED = MessageTemplate(
        message_code="ANNOUNCEMENT_UPDATED",
        message_params=[],
        message_template="Announcement updated successfully",
    )

    INVALID_ANNOUNCEMENT_DATA = MessageTemplate(
        message_code="INVALID_ANNOUNCEMENT_DATA",
        message_params=["details"],
        message_template="Invalid announcement data: {details}",
    )

    DEVICE_NOT_FOUND = MessageTemplate(
        message_code="DEVICE_NOT_FOUND",
        message_params=["id"],
        message_template="device_id={id} is not found.",
    )

    DEVICE_ALREADY_EXISTS = MessageTemplate(
        message_code="DEVICE_ALREADY_EXISTS",
        message_params=["id"],
        message_template="device_id={id} already exists",
    )

    INVALID_DEVICE_TIMEZONE = MessageTemplate(
        message_code="INVALID_DEVICE_TIMEZONE",
        message_params=["id"],
        message_template="Invalid timezone for device_id={id}",
    )

    DEVICE_REGISTERED = MessageTemplate(
        message_code="DEVICE_REGISTERED",
        message_params=[],
        message_template="Device registered successfully",
    )

    INCONSISTENT_DEVICE_ID = MessageTemplate(
        message_code="INCONSISTENT_DEVICE_ID",
        message_params=["id1", "id2"],
        message_template="device_id is inconsistent with device_info: {id1} != {id2}",
    )

    DEVICE_UPDATED = MessageTemplate(
        message_code="DEVICE_UPDATED",
        message_params=[],
        message_template="Device updated successfully",
    )

    DEVICE_DELETED = MessageTemplate(
        message_code="DEVICE_DELETED",
        message_params=[],
        message_template="Device deleted successfully",
    )

    INVALID_USER_STATUS = MessageTemplate(
        message_code="INVALID_USER_STATUS",
        message_params=["status"],
        message_template="Invalid user status: {status}",
    )

    INVALID_SORT_PARAMETER = MessageTemplate(
        message_code="INVALID_SORT_PARAMETER",
        message_params=["sort"],
        message_template="Invalid sort parameter: {sort}",
    )

    INVALID_SORT_COLUMN = MessageTemplate(
        message_code="INVALID_SORT_COLUMN",
        message_params=["column"],
        message_template="Invalid column name to sort: {column}",
    )
    INVALID_SORT_ORDER = MessageTemplate(
        message_code="INVALID_SORT_ORDER",
        message_params=["order"],
        message_template="Invalid order to sort: {order}",
    )

    USER_NOT_FOUND = MessageTemplate(
        message_code="USER_NOT_FOUND",
        message_params=["id"],
        message_template="user_id={id} is not found.",
    )

    FIELD_REQUIRED = MessageTemplate(
        message_code="FIELD_REQUIRED",
        message_params=["field"],
        message_template="{field} is required.",
    )

    FIELD_TOO_LONG = MessageTemplate(
        message_code="FIELD_TOO_LONG",
        message_params=["field", "limit"],
        message_template="The length of {field} exceeds the limit. Please enter within {limit} characters",
    )

    EMAIL_ALREADY_EXISTS = MessageTemplate(
        message_code="EMAIL_ALREADY_EXISTS",
        message_params=["email"],
        message_template="{email} is already registered.",
    )

    NO_USERS_TO_REGISTER = MessageTemplate(
        message_code="NO_USERS_TO_REGISTER",
        message_params=[],
        message_template="No users to register.",
    )

    NO_VALID_USER_TO_REGISTER = MessageTemplate(
        message_code="NO_VALID_USER_TO_REGISTER",
        message_params=[],
        message_template="No valid user to register.",
    )

    WHITELIST_USER_REGISTERED = MessageTemplate(
        message_code="WHITELIST_USER_REGISTERED",
        message_params=[],
        message_template="Whitelist user registered successfully",
    )

    USER_NOT_IN_WHITELIST = MessageTemplate(
        message_code="USER_NOT_IN_WHITELIST",
        message_params=["id"],
        message_template="Not in whitelist_users: {id}",
    )

    SIGNUP_CONFIRMATION_FAILED = MessageTemplate(
        message_code="SIGNUP_CONFIRMATION_FAILED",
        message_params=["details"],
        message_template="Failed to confirm signup: {details}",
    )

    AUTHENTICATION_FAILED = MessageTemplate(
        message_code="AUTHENTICATION_FAILED",
        message_params=[],
        message_template="Failed to authenticate user",
    )

    MFA_ALREADY_ENABLED = MessageTemplate(
        message_code="MFA_ALREADY_ENABLED",
        message_params=["id"],
        message_template="MFA is already enabled for user: {id}",
    )

    CODE_VERIFICATION_FAILED = MessageTemplate(
        message_code="CODE_VERIFICATION_FAILED",
        message_params=[],
        message_template="Failed to verify the code.",
    )

    INVALID_TOTP_CODE = MessageTemplate(
        message_code="INVALID_TOTP_CODE",
        message_params=[],
        message_template="Invalid TOTP code.",
    )

    OPERATION_SUCCESSFUL = MessageTemplate(
        message_code="OPERATION_SUCCESSFUL",
        message_params=[],
        message_template="Operation completed successfully.",
    )

    INTERNAL_SERVER_ERROR = MessageTemplate(
        message_code="INTERNAL_SERVER_ERROR",
        message_params=[],
        message_template="Internal Server Error",
    )

    def format(self, **kwargs) -> Message:
        """
        Helper to construct the dictionary response.
        Validates that you passed the required parameters.
        """
        # validation: check if provided kwargs match required params
        required = set(self.value.message_params)
        provided = set(kwargs.keys())

        if not required.issubset(provided):
            missing = required - provided
            raise ValueError(
                f"Code {self.value.message_code} requires params: {missing}"
            )

        return Message(
            message_code=self.value.message_code,
            message_params=kwargs,
            message=self.value.message_template.format(**kwargs),
        )
