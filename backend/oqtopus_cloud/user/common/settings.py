import json
from os import environ

from oqtopus_cloud.user.schemas.settings import EditableField


def get_editable_fields() -> list[EditableField]:
    try:
        editable_fields = json.loads(environ.get("EDITABLE_FIELDS", "[]"))
        if not isinstance(editable_fields, list):
            editable_fields = []

        return [EditableField(v) for v in editable_fields]
    except Exception:
        return []
