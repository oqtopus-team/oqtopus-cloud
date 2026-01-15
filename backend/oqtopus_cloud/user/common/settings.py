import json
from os import environ

from oqtopus_cloud.user.schemas.settings import EditableField, VisibleField


def get_editable_fields() -> list[EditableField]:
    try:
        editable_fields = json.loads(environ.get("EDITABLE_FIELDS", "[]"))
        if not isinstance(editable_fields, list):
            editable_fields = []

        return [EditableField(v) for v in editable_fields]
    except Exception:
        return []


def get_visible_fields() -> list[VisibleField]:
    try:
        visible_fields = json.loads(environ.get("VISIBLE_FIELDS", "[]"))
        if not isinstance(visible_fields, list):
            visible_fields = []

        return [VisibleField(v) for v in visible_fields]
    except Exception:
        return []
