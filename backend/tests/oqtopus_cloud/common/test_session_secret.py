import json
import os

import pytest
from sqlalchemy.engine import make_url

from oqtopus_cloud.common import session
from oqtopus_cloud.common.secret_file import InsecureSecretFile


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "local")
    monkeypatch.delenv("DB_USERNAME", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_SECRET_FILE", raising=False)
    monkeypatch.delenv("DB_CREDENTIAL_SOURCE", raising=False)


def _write_secret(tmp_path, data, mode=0o600) -> str:
    p = tmp_path / "db-secret.json"
    p.write_text(json.dumps(data))
    os.chmod(p, mode)
    return str(p)


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


# --- credential source selection (explicit, not inferred) --------------------


def test_source_defaults_local_for_env_local() -> None:
    assert session.db_credential_source() == "local"


def test_source_defaults_aws_for_non_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    assert session.db_credential_source() == "aws"


def test_source_explicit_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    assert session.db_credential_source() == "file"


def test_unknown_source_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "vault")
    with pytest.raises(RuntimeError, match="invalid"):
        session.db_credential_source()
    with pytest.raises(RuntimeError, match="invalid"):
        session.get_secret()


# --- file-injected DB credentials (on-prem), fail-closed ---------------------


def test_secret_file_takes_precedence_over_env_and_aws(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # source=file is authoritative even with ENV=prod and a stray DB_USERNAME.
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DB_USERNAME", "ignored")
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    path = _write_secret(tmp_path, {"username": "svc", "password": "p@ss"})
    monkeypatch.setenv("DB_SECRET_FILE", path)
    assert session.get_secret() == {"username": "svc", "password": "p@ss"}


def test_source_file_requires_secret_file(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail-closed: file mode with no DB_SECRET_FILE must NOT fall back.
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    monkeypatch.delenv("DB_SECRET_FILE", raising=False)
    with pytest.raises(RuntimeError, match="DB_SECRET_FILE"):
        session.get_secret()


def test_source_file_rejects_invalid_json(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "db-secret.json"
    p.write_text("not json")
    os.chmod(p, 0o600)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    monkeypatch.setenv("DB_SECRET_FILE", str(p))
    with pytest.raises(InsecureSecretFile):
        session.get_secret()


def test_secret_file_rejects_group_readable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_secret(tmp_path, {"username": "svc", "password": "p@ss"}, mode=0o640)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    monkeypatch.setenv("DB_SECRET_FILE", path)
    with pytest.raises(InsecureSecretFile):
        session.get_secret()


def test_secret_file_rejects_empty_username(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_secret(tmp_path, {"username": "", "password": "p@ss"})
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    monkeypatch.setenv("DB_SECRET_FILE", path)
    with pytest.raises(RuntimeError, match="non-empty"):
        session.get_secret()


# --- validate_db_runtime_config ----------------------------------------------


def _set_db_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.setenv("DB_CONNECTOR", "mysql+pymysql")


def test_validate_requires_each_db_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.delenv("DB_CONNECTOR", raising=False)
    with pytest.raises(RuntimeError, match="DB_CONNECTOR"):
        session.validate_db_runtime_config()


def test_validate_rejects_unknown_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.setenv("DB_CONNECTOR", "postgresql+psycopg2")
    with pytest.raises(RuntimeError, match="not allowed"):
        session.validate_db_runtime_config()


def test_validate_passes_for_local_source(monkeypatch: pytest.MonkeyPatch) -> None:
    # ENV=local (fixture) -> local source: 3 vars + connector are enough.
    _set_db_vars(monkeypatch)
    session.validate_db_runtime_config()  # no raise


def test_validate_file_mode_checks_secret(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    path = _write_secret(tmp_path, {"username": "svc", "password": "p@ss"})
    monkeypatch.setenv("DB_SECRET_FILE", path)
    session.validate_db_runtime_config()  # no raise


def test_validate_file_mode_fails_without_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    monkeypatch.delenv("DB_SECRET_FILE", raising=False)
    with pytest.raises(RuntimeError, match="DB_SECRET_FILE"):
        session.validate_db_runtime_config()


def test_validate_rejects_malformed_secret_shape(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    path = _write_secret(tmp_path, {"username": "svc"})  # missing password
    monkeypatch.setenv("DB_SECRET_FILE", path)
    with pytest.raises(RuntimeError, match="non-empty"):
        session.validate_db_runtime_config()


# --- build_db_url: safe handling of URL-significant characters ----------------


def test_build_db_url_preserves_special_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A strong random password with @ : / % must be carried as a component, not
    # interpolated into the URL string (where "p@ss" would parse as password "p"
    # and host "ss@...").
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_USERNAME", "us@r")
    monkeypatch.setenv("DB_PASSWORD", "p@ss:w/rd%41")  # ENV=local -> local source
    url = session.build_db_url()
    assert url.drivername == "mysql+pymysql"
    assert url.username == "us@r"
    assert url.password == "p@ss:w/rd%41"
    assert url.host == "db"
    assert url.database == "main"
    # Round-trip through a rendered string must preserve the exact password.
    rendered = url.render_as_string(hide_password=False)
    assert make_url(rendered).password == "p@ss:w/rd%41"


def test_build_db_url_splits_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_HOST", "dbhost:3307")
    monkeypatch.setenv("DB_USERNAME", "svc")
    monkeypatch.setenv("DB_PASSWORD", "pw")
    url = session.build_db_url()
    assert url.host == "dbhost"
    assert url.port == 3307


def test_build_db_url_uses_file_credentials(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The same escaping applies when credentials come from the on-prem file.
    _set_db_vars(monkeypatch)
    monkeypatch.setenv("DB_CREDENTIAL_SOURCE", "file")
    path = _write_secret(tmp_path, {"username": "svc", "password": "p@ss/w:rd"})
    monkeypatch.setenv("DB_SECRET_FILE", path)
    url = session.build_db_url()
    assert url.username == "svc"
    assert url.password == "p@ss/w:rd"
