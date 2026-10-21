import pytest

from oqtopus_cloud.common import db_tls


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("DB_SSL_CA", raising=False)


def test_bundled_ca_is_the_default() -> None:
    assert db_tls.ssl_ca_path() == db_tls.DEFAULT_DB_SSL_CA
    assert db_tls.DEFAULT_DB_SSL_CA.endswith("certs/global-bundle.pem")


def test_bundled_ca_exists() -> None:
    # A missing bundle would only surface as a TLS failure at connect time.
    with open(db_tls.DEFAULT_DB_SSL_CA, encoding="ascii") as bundle:
        assert "BEGIN CERTIFICATE" in bundle.read()


def test_ca_is_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_SSL_CA", "/custom/ca.pem")
    assert db_tls.ssl_ca_path() == "/custom/ca.pem"


def test_local_disables_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "local")
    assert db_tls.ssl_connect_args("localhost") == {}


def test_remote_host_verifies_hostname() -> None:
    args = db_tls.ssl_connect_args("oqtopus.proxy-abc.ap-northeast-1.rds.amazonaws.com")
    assert args == {"ssl": {"ca": db_tls.DEFAULT_DB_SSL_CA}}


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_port_forward_keeps_tls_but_skips_hostname_check(host: str) -> None:
    # The RDS Proxy certificate names the proxy, never the local end of the
    # tunnel, so hostname verification can never succeed here. The CA must
    # still be presented, otherwise the proxy rejects the connection.
    args = db_tls.ssl_connect_args(host)
    assert args == {"ssl": {"ca": db_tls.DEFAULT_DB_SSL_CA, "check_hostname": False}}


def test_unknown_host_keeps_hostname_check() -> None:
    assert "check_hostname" not in db_tls.ssl_connect_args(None)["ssl"]
