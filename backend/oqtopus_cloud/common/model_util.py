import re
from enum import Enum
from typing import Any, Callable, Dict, Type, TypeVar

from sqlalchemy import JSON, String, TypeDecorator


def model_to_dict(model: Any) -> Dict[Any, Any]:
    dict_obj: Dict[Any, Any] = model.__dict__
    if "_sa_instance_state" in dict_obj:
        del dict_obj["_sa_instance_state"]
    return dict_obj


def model_to_schema_dict(
    model: Any, map_model_to_schema: Dict[str, str]
) -> Dict[str, Any]:
    model_dict = model_to_dict(model)
    schema_dict = dict()
    for model_field, schema_field in map_model_to_schema.items():
        schema_dict[schema_field] = model_dict[model_field]
    return schema_dict


T = TypeVar("T", bound=Enum)


class JsonType(TypeDecorator):
    impl = JSON

    def __init__(
        self, encoder: Callable[[Type[T]], Any], decoder: Callable[[Any], Type[T]]
    ):
        super(JsonType, self).__init__()
        self.encoder = encoder
        self.decoder = decoder

    def process_bind_param(self, value, dialect):
        return self.encoder(value)

    def process_result_value(self, value, dialect):
        return self.decoder(value)


class StringList(TypeDecorator):
    impl = String

    def __init__(self, item_type):
        super().__init__()
        self.item_type = item_type

    def process_bind_param(self, value, dialect):
        # if not isinstance(value, list):
        #     raise ValueError("value should be a list")

        def process_value(v):
            # if isinstance(self.item_type, TypeEngine):
            #     bind_proccessor = self.item_type.bind_processor(dialect)
            #     if bind_proccessor is not None:
            #         return bind_proccessor(v)

            # elif isinstance(self.item_type, TypeDecorator):
            #     return self.item_type.process_bind_param(v, dialect)

            if isinstance(self.item_type, TypeDecorator):
                return self.item_type.process_bind_param(v, dialect)
            return None

        def escape(s):
            return s.replace(",", r"\,") if isinstance(s, str) else str(s)

        return ",".join([escape(process_value(v)) for v in value])

    def process_result_value(self, value, dialect):
        def unescape(s):
            return re.sub(r"(?<!\\)\\,", ",", s)

        def process_value(s):
            if isinstance(self.item_type, TypeDecorator):
                return self.item_type.process_result_value(s, dialect)
            return s

        return [
            process_value(unescape(s)) for s in re.split(r"(?<!\\),(?!\s|$)", value)
        ]


class StringEnumType(TypeDecorator):
    """#TODO Describe usage

    Args:
        TypeDecorator (_type_): _description_

    Raises:
        ValueError: _description_

    Returns:
        _type_: _description_
    """

    impl = String(128)

    def __init__(self, enum_type: Type[T]):
        super(StringEnumType, self).__init__()
        self.enum_type = enum_type

    def process_bind_param(self, value, dialect):
        if isinstance(value, self.enum_type):
            return value.value
        raise ValueError(
            "expected %s value, got %s"
            % (self.enum_type.__name__, value.__class__.__name__)
        )

    def process_result_value(self, value, dialect):
        return self.enum_type(value)

    def copy(self, **kwargs):
        return StringEnumType(self.enum_type)
