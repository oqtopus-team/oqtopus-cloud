from oqtopus_cloud.user.common.settings import get_editable_fields
from oqtopus_cloud.user.schemas.settings import EditableField


def test_get_editable_fields(monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", '["name", "organization"]')
    actual = get_editable_fields()
    expected = [EditableField("name"), EditableField("organization")]
    assert actual == expected


def test_get_editable_fields_empty_by_default(monkeypatch):
    monkeypatch.delenv("EDITABLE_FIELDS")
    assert get_editable_fields() == []


def test_get_editable_fields_empty_when_invalid_json(monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", 'invalid json')
    assert get_editable_fields() == []


def test_get_editable_fields_empty_when_not_a_list(monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", '"not-a-list"')
    assert get_editable_fields() == []


def test_get_editable_fields_empty_when_unexpected_fields(monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", '["name", "differentName"]')
    assert get_editable_fields() == []