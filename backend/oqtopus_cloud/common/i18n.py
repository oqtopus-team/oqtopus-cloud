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

    DEVICE_ID_REQUIRED = MessageTemplate(
        message_code="DEVICE_ID_REQUIRED",
        message_params=[],
        message_template="device_id is required",
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
