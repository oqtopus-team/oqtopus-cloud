import importlib

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

ROUTER_MODULES = [
    "oqtopus_cloud.user.routers",
    "oqtopus_cloud.provider.routers",
    "oqtopus_cloud.admin.routers",
    "oqtopus_cloud.user_signup.routers",
]


class RecordingLogger:
    def __init__(self):
        self.calls = []

    def append_keys(self, **_keys):
        pass

    def info(self, message, **kwargs):
        self.calls.append(("info", message, kwargs))

    def error(self, message, **kwargs):
        self.calls.append(("error", message, kwargs))


@pytest.fixture(params=ROUTER_MODULES)
def client_and_logger(request, monkeypatch):
    module = importlib.import_module(request.param)
    recorder = RecordingLogger()
    monkeypatch.setattr(module, "logger", recorder)

    router = APIRouter(route_class=module.LoggerRouteHandler)

    @router.get("/ok")
    def ok():
        return {"ok": True}

    @router.get("/client-error")
    def client_error():
        raise HTTPException(status_code=404, detail="not found")

    @router.get("/server-error")
    def server_error():
        raise RuntimeError("boom")

    @router.get("/needs-query")
    def needs_query(value: int):
        return {"value": value}

    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False), recorder


def _completion(recorder):
    calls = [c for c in recorder.calls if c[1] == "Request completed"]
    assert len(calls) == 1, recorder.calls
    return calls[0]


def test_success_logged_at_info(client_and_logger):
    client, recorder = client_and_logger
    assert client.get("/ok").status_code == 200
    level, _, kwargs = _completion(recorder)
    assert level == "info"
    assert kwargs["extra"] == {"status_code": 200}


def test_client_error_logged_at_info(client_and_logger):
    client, recorder = client_and_logger
    assert client.get("/client-error").status_code == 404
    level, _, kwargs = _completion(recorder)
    assert level == "info"
    assert kwargs["extra"] == {"status_code": 404}


def test_validation_error_logged_at_info(client_and_logger):
    client, recorder = client_and_logger
    assert client.get("/needs-query").status_code == 422
    level, _, kwargs = _completion(recorder)
    assert level == "info"
    assert kwargs["extra"] == {"status_code": 422}


def test_server_error_promoted_to_error(client_and_logger):
    client, recorder = client_and_logger
    assert client.get("/server-error").status_code == 500
    level, _, kwargs = _completion(recorder)
    assert level == "error"
    assert kwargs["extra"] == {"status_code": 500}
