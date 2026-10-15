import pytest

from oqtopus_cloud.common import session


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("DB_USERNAME", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)


def test_local_defaults_when_unset() -> None:
    assert session.get_secret() == {"username": "admin", "password": "password"}


def test_local_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USERNAME", "alice")
    monkeypatch.setenv("DB_PASSWORD", "s3cret")
    assert session.get_secret() == {"username": "alice", "password": "s3cret"}


def test_non_local_ignores_db_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DB_USERNAME", "alice")
    monkeypatch.delenv("SECRET_NAME", raising=False)
    with pytest.raises(KeyError):
        session.get_secret()
