from oqtopus_cloud.user.schemas.settings import EditableField, VisibleField, GetSettingsResponse
from pydantic import TypeAdapter
from unittest import mock

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
        visible_fields=[VisibleField("id"), VisibleField("email"), VisibleField("name"), VisibleField("organization"), VisibleField("created_at")],
        login_history_enabled=True,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_custom_settings(test_client, monkeypatch):
    monkeypatch.setenv("ALLOW_DELETION", "false")
    monkeypatch.setenv("EDITABLE_FIELDS", '["organization"]')
    monkeypatch.setenv("VISIBLE_FIELDS", '["id", "name"]')
    monkeypatch.setenv("LOGIN_HISTORY_ENABLED", 'false')

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[EditableField("organization")],
        allow_deletion=False,
        visible_fields=[VisibleField("id"), VisibleField("name")],
        login_history_enabled=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_should_send_defaults_when_no_settings_set(test_client, monkeypatch):
    monkeypatch.delenv("ALLOW_DELETION")
    monkeypatch.delenv("EDITABLE_FIELDS")
    monkeypatch.delenv("VISIBLE_FIELDS")
    monkeypatch.delenv("LOGIN_HISTORY_ENABLED")

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[],
        allow_deletion=False,
        visible_fields=[],
        login_history_enabled=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_should_send_defaults_incorrect_fields_format(test_client, monkeypatch):
    monkeypatch.setenv("ALLOW_DELETION", "false")
    monkeypatch.setenv("EDITABLE_FIELDS", '"not_a_list"')
    monkeypatch.setenv("VISIBLE_FIELDS", '"not_a_list"')
    monkeypatch.setenv("LOGIN_HISTORY_ENABLED", "false")

    response = test_client.get("/system/settings")
    adapter = TypeAdapter(GetSettingsResponse)
    actual = adapter.validate_python(response.json())

    expected = GetSettingsResponse(
        editable_fields=[],
        allow_deletion=False,
        visible_fields=[],
        login_history_enabled=False,
    )

    assert response.status_code == 200
    assert actual == expected


def test_get_settings_500(test_client, monkeypatch):
    monkeypatch.setenv("EDITABLE_FIELDS", 'invalid json')
    response = None
    with mock.patch("oqtopus_cloud.user.routers.settings.get_editable_fields", side_effect=Exception("error")):
        response = test_client.get("/system/settings")
    assert response.status_code == 500
