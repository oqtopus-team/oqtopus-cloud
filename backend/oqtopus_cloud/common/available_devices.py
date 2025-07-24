import json
from pydantic import TypeAdapter
from typing import Literal

type_adapter = TypeAdapter(list[str])


def parse_available_devices_string(
    available_devices: str | None,
) -> list[str] | Literal["*"] | None:
    if available_devices is None:
        return None

    if available_devices == "*":
        return "*"

    return type_adapter.validate_json(available_devices)


def convert_available_devices_to_string(
    available_devices: list[str] | Literal["*"] | None,
) -> str | None:
    match available_devices:
        case None:
            return None
        case "*":
            return "*"
        case _:
            return json.dumps(available_devices)
