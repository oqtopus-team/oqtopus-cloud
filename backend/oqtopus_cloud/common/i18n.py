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

    FORBIDDEN_USER_SUSPENDED = MessageTemplate(
        message_code="FORBIDDEN_USER_SUSPENDED",
        message_params=[],
        message_template="Forbidden: user status is suspended.",
    )

    FORBIDDEN_DEVICE_ACCESS = MessageTemplate(
        message_code="FORBIDDEN_DEVICE_ACCESS",
        message_params=["id"],
        message_template="Forbidden: cannot access device_id={id}.",
    )

    INVALID_FIELDS = MessageTemplate(
        message_code="INVALID_FIELDS",
        message_params=["fields"],
        message_template="Invalid fields in request: {fields}.",
    )

    DEVICE_NOT_AVAILABLE = MessageTemplate(
        message_code="DEVICE_NOT_AVAILABLE",
        message_params=["id"],
        message_template="Device_id={id} is not available.",
    )

    JOB_INFO_INCOMPATIBLE_WITH_JOB_TYPE = MessageTemplate(
        message_code="JOB_INFO_INCOMPATIBLE_WITH_JOB_TYPE",
        message_params=[],
        message_template="job_info is not compatible with job_type.",
    )

    JOB_NOT_FOUND = MessageTemplate(
        message_code="JOB_NOT_FOUND",
        message_params=["id"],
        message_template="job_id={id} is not found.",
    )

    JOB_INVALID_STATUS_FOR_DELETION = MessageTemplate(
        message_code="JOB_INVALID_STATUS_FOR_DELETION",
        message_params=["id"],
        message_template="job_id={id} is not in valid status for deletion (valid statuses for deletion: 'succeeded', 'failed' and 'cancelled')",
    )

    JOB_DELETED = MessageTemplate(
        message_code="JOB_DELETED",
        message_params=[],
        message_template="Job deleted successfully.",
    )

    JOB_INVALID_STATUS_FOR_CANCELLATION = MessageTemplate(
        message_code="JOB_INVALID_STATUS_FOR_DELETION",
        message_params=["id"],
        message_template="job_id={id} is not in valid status for cancellation (valid statuses for cancellation: 'ready', 'submitted' and 'running')",
    )

    JOB_CANCELLING_ACCEPTED = MessageTemplate(
        message_code="JOB_CANCELLING_ACCEPTED",
        message_params=[],
        message_template="Job cancellation request accepted.",
    )

    JOB_NOT_SSE = MessageTemplate(
        message_code="JOB_NOT_SSE",
        message_params=[],
        message_template="Job is not an SSE job",
    )

    JOB_NOT_FINISHED = MessageTemplate(
        message_code="JOB_NOT_FINISHED",
        message_params=[],
        message_template="Job has not finished yet",
    )

    LOG_FILE_NOT_FOUND = MessageTemplate(
        message_code="LOG_FILE_NOT_FOUND",
        message_params=[],
        message_template="Log file not found.",
    )

    FIELD_DISABLED_FOR_UPDATES = MessageTemplate(
        message_code="FIELD_DISABLED_FOR_UPDATES",
        message_params=["field"],
        message_template="Field is disabled for updates: {field}",
    )

    USER_DELETION_DISABLED = MessageTemplate(
        message_code="USER_DELETION_DISABLED",
        message_params=[],
        message_template="User deletion is disabled.",
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
