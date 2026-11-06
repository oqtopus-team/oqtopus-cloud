from sqlalchemy import create_engine as sqlalchemy_create_engine

from oqtopus_cloud.common import session


def test_create_session_reuses_bounded_engine(monkeypatch):
    created_engines = []

    def fake_create_engine(database_url, **kwargs):
        engine = sqlalchemy_create_engine("sqlite:///:memory:")
        created_engines.append((database_url, kwargs, engine))
        return engine

    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.setenv("DB_CONNECTOR", "mysql+pymysql")
    monkeypatch.setattr(
        session, "get_secret", lambda: {"username": "admin", "password": "password"}
    )
    monkeypatch.setattr(session, "ssl_connect_args", lambda host: {})
    monkeypatch.setattr(session, "create_engine", fake_create_engine)
    session._dispose_cached_engines()

    first = session._create_session()
    second = session._create_session()

    assert len(created_engines) == 1
    assert first.get_bind() is second.get_bind()
    assert created_engines[0][1]["pool_size"] == 5
    assert created_engines[0][1]["max_overflow"] == 0
    assert created_engines[0][1]["pool_timeout"] == 30

    first.close()
    second.close()
    session._dispose_cached_engines()


def test_authorizer_uses_separate_shared_engine(monkeypatch):
    created_engines = []

    def fake_create_engine(database_url, **kwargs):
        engine = sqlalchemy_create_engine("sqlite:///:memory:")
        created_engines.append((database_url, kwargs, engine))
        return engine

    monkeypatch.setenv("ENV", "local")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.setenv("DB_CONNECTOR", "mysql+pymysql")
    monkeypatch.setattr(
        session, "get_secret", lambda: {"username": "admin", "password": "password"}
    )
    monkeypatch.setattr(session, "ssl_connect_args", lambda host: {})
    monkeypatch.setattr(session, "create_engine", fake_create_engine)
    session._dispose_cached_engines()

    normal = session._create_session()
    authorizer = session._create_session(read_timeout=5)

    assert len(created_engines) == 2
    assert "read_timeout" not in created_engines[0][1]["connect_args"]
    assert created_engines[1][1]["connect_args"]["read_timeout"] == 5

    normal.close()
    authorizer.close()
    session._dispose_cached_engines()
