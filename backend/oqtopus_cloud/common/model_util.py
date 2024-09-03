from typing import Any, Dict


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
