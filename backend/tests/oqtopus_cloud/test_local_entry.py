import pytest

from oqtopus_cloud import local_entry


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "UVICORN_HOST",
        "UVICORN_PORT",
        "UVICORN_LOG_LEVEL",
        "USER_API_LOG_LEVEL",
        "USER_API_URL",
        "PROVIDER_API_LOG_LEVEL",
        "POWERTOOLS_SERVICE_NAME",
        "POWERTOOLS_METRICS_NAMESPACE",
        "USER_API_POWERTOOLS_SERVICE_NAME",
        "PROVIDER_API_POWERTOOLS_SERVICE_NAME",
    ):
        monkeypatch.delenv(key, raising=False)


def test_option_names_are_read_from_uvicorn() -> None:
    names = local_entry._uvicorn_option_names()
    assert {"HOST", "PORT", "RELOAD", "LOG_LEVEL"} <= names
    assert "APP" not in names


def test_scoped_value_overrides_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UVICORN_LOG_LEVEL", "debug")
    monkeypatch.setenv("USER_API_LOG_LEVEL", "warning")
    local_entry.apply_scoped_uvicorn_env("USER_API")
    assert local_entry.os.environ["UVICORN_LOG_LEVEL"] == "warning"


def test_other_scope_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_API_LOG_LEVEL", "warning")
    local_entry.apply_scoped_uvicorn_env("USER_API")
    assert "UVICORN_LOG_LEVEL" not in local_entry.os.environ


def test_non_uvicorn_option_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_API_URL", "http://localhost")
    local_entry.apply_scoped_uvicorn_env("USER_API")
    assert "UVICORN_URL" not in local_entry.os.environ


def test_empty_value_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USER_API_LOG_LEVEL", "")
    local_entry.apply_scoped_uvicorn_env("USER_API")
    assert "UVICORN_LOG_LEVEL" not in local_entry.os.environ


def test_run_applies_defaults_and_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(local_entry, "_start_uvicorn", lambda app: calls.append(app))
    monkeypatch.setenv("UVICORN_HOST", "")
    monkeypatch.setenv("USER_API_PORT", "8080")
    monkeypatch.setenv("USER_API_LOG_LEVEL", "info")
    local_entry.run_user()
    env = local_entry.os.environ
    assert env["UVICORN_HOST"] == "127.0.0.1"
    assert env["UVICORN_PORT"] == "8080"
    assert env["UVICORN_LOG_LEVEL"] == "info"
    assert calls[0] == "oqtopus_cloud.user.lambda_function:app"
    monkeypatch.delenv("UVICORN_HOST")
    monkeypatch.delenv("UVICORN_PORT")
    monkeypatch.delenv("UVICORN_LOG_LEVEL")


def test_run_requires_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USER_API_PORT", raising=False)
    monkeypatch.setattr(local_entry, "_start_uvicorn", lambda app: None)
    with pytest.raises(SystemExit, match="USER_API_PORT"):
        local_entry.run_user()


def test_powertools_defaults_and_scoped_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("USER_API_PORT", "8080")
    monkeypatch.setenv("USER_API_POWERTOOLS_SERVICE_NAME", "custom")
    monkeypatch.setenv("PROVIDER_API_POWERTOOLS_SERVICE_NAME", "other")
    monkeypatch.setattr(local_entry, "_start_uvicorn", lambda app: None)
    local_entry.run_user()
    env = local_entry.os.environ
    assert env["POWERTOOLS_SERVICE_NAME"] == "custom"
    assert env["POWERTOOLS_METRICS_NAMESPACE"] == "user-api"
    monkeypatch.delenv("UVICORN_HOST")
    monkeypatch.delenv("UVICORN_PORT")


def test_user_signup_scope_and_service_name() -> None:
    assert local_entry.USER_SIGNUP.scope == "USER_SIGNUP_API"
    assert local_entry.USER_SIGNUP.name == "user_signup-api"
