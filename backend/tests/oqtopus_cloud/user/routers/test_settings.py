from oqtopus_cloud.user.schemas.settings import EditableField, GetSettingsResponse
from pydantic import TypeAdapter

from fastapi.testclient import TestClient
from oqtopus_cloud.user.lambda_function import app

client = TestClient(app)


def test_get_settings(test_client):
    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[EditableField("name"), EditableField("organization")],
        allow_deletion=True,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_custom_settings(test_client, monkeypatch):
    monkeypatch.setenv("ALLOW_DELETION", "false")
    monkeypatch.setenv("EDITABLE_FIELDS", '["organization"]')

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[EditableField("organization")],
        allow_deletion=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_should_send_defaults_when_no_settings_set(test_client, monkeypatch):
    monkeypatch.delenv("ALLOW_DELETION")
    monkeypatch.delenv("EDITABLE_FIELDS")

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[],
        allow_deletion=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_should_send_defaults_incorrect_fields_format(test_client, monkeypatch):
    monkeypatch.setenv("ALLOW_DELETION", "false")
    monkeypatch.setenv("EDITABLE_FIELDS", '"not_a_list"')

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[],
        allow_deletion=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_500(test_client, monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", 'invalid json')
    response = test_client.get("/system/settings")
    assert response.status_code == 500
