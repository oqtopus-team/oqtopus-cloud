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

    ANNOUNCEMENT_NOT_FOUND = MessageTemplate(
        message_code="ANNOUNCEMENT_NOT_FOUND",
        message_params=["id"],
        message_template="announcement_id={id} is not found.",
    )

    INVALID_ANNOUNCEMENT_DATA = MessageTemplate(
        message_code="INVALID_ANNOUNCEMENT_DATA",
        message_params=["details"],
        message_template="Invalid announcement data: {details}",
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
