import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from oqtopus_cloud import infra


class FakeRun:
    """Stand-in for ``infra._run`` that records commands."""

    def __init__(
        self, running: str = "", returncode: int = 0, init_exit: int = 0
    ) -> None:
        self.init_exit = init_exit
        self.calls: list[list[str]] = []
        self.envs: list[Any] = []
        self.running = running
        self.returncode = returncode

    def __call__(self, cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        self.envs.append(kwargs.get("env"))
        stdout = ""
        if "--format" in cmd:
            stdout = json.dumps({"State": "exited", "ExitCode": self.init_exit})
        elif "ps" in cmd:
            stdout = self.running
        return subprocess.CompletedProcess(cmd, self.returncode, stdout, "")


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("STORAGE_STACK", "STORAGE_DRIVER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_NAME", "main")
    monkeypatch.setenv("DB_USERNAME", "admin")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    monkeypatch.setattr(infra.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(infra.time, "sleep", lambda _: None)


@pytest.fixture
def fake_run(monkeypatch: pytest.MonkeyPatch) -> FakeRun:
    fake = FakeRun()
    monkeypatch.setattr(infra, "_run", fake)
    return fake


def exit_code(*argv: str) -> int:
    with pytest.raises(SystemExit) as info:
        infra.main(list(argv))
    assert isinstance(info.value.code, int)
    return info.value.code


# --- stack resolution -------------------------------------------------------


def test_apply_stack_env_overwrites_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "minio")
    monkeypatch.setenv("STORAGE_DRIVER", "whatever")
    assert infra.apply_stack_env() == "minio"
    assert infra.os.environ["STORAGE_DRIVER"] == "local:minio"


def test_apply_stack_env_seaweedfs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    infra.apply_stack_env()
    assert infra.os.environ["STORAGE_DRIVER"] == "seaweedfs"


@pytest.mark.parametrize("value", [None, ""])
def test_apply_stack_env_unset_or_empty_is_noop(
    monkeypatch: pytest.MonkeyPatch, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv("STORAGE_STACK", value)
    monkeypatch.setenv("STORAGE_DRIVER", "keep")
    assert infra.apply_stack_env() is None
    assert infra.os.environ["STORAGE_DRIVER"] == "keep"


def test_apply_stack_env_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "nope")
    with pytest.raises(infra.ConfigError):
        infra.apply_stack_env()


def test_stacks_table() -> None:
    assert infra.STACKS["seaweedfs"] == infra.Stack(
        "seaweedfs", "seaweedfs", "seaweedfs-bucket-init", None
    )
    assert infra.STACKS["minio"] == infra.Stack("local:minio", "minio", "mc", "minio")


# --- exit codes -------------------------------------------------------------


@pytest.mark.parametrize("command", ["start", "stop"])
@pytest.mark.parametrize("value", [None, "", "nope"])
def test_start_stop_without_valid_stack_exit_6(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun, command: str, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv("STORAGE_STACK", value)
    assert exit_code(command) == 6
    assert fake_run.calls == []


@pytest.mark.parametrize("argv", [[], ["restart"], ["version"]])
def test_invalid_arguments_exit_2(argv: list[str]) -> None:
    assert exit_code(*argv) == 2


@pytest.mark.parametrize("command", ["start", "stop"])
def test_missing_docker_exits_5(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun, command: str
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra.shutil, "which", lambda _: None)
    assert exit_code(command) == 5


def test_start_without_db_settings_exits_6(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.delenv("DB_PASSWORD")
    assert exit_code("start") == 6


# --- start ------------------------------------------------------------------


def test_start_runs_steps_in_order(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "minio")
    monkeypatch.setenv("STORAGE_DRIVER", "seaweedfs")
    monkeypatch.setattr(infra, "_host_port_ready", lambda: True)
    assert exit_code("start") == 0

    calls = fake_run.calls
    assert calls[0][-3:] == ["stop", "seaweedfs", "seaweedfs-bucket-init"]
    assert calls[1][-5:] == ["up", "-d", "db", "minio", "mc"]
    assert "mysql" in calls[2]
    assert calls[3][-3:] == ["alembic", "upgrade", "head"]
    assert calls[4][-1] == "scripts/seed.py"
    assert calls[5][-5:] == ["ps", "-a", "--format", "json", "mc"]
    assert calls[6][-1] == "storage/init_storage.py"
    assert infra.os.environ["STORAGE_DRIVER"] == "local:minio"


def test_start_passes_password_through_environment(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra, "_host_port_ready", lambda: True)
    exit_code("start")
    mysql = next(c for c in fake_run.calls if "mysql" in c)
    assert not any("secret" in arg for arg in mysql)
    assert "MYSQL_PWD" in mysql
    env = fake_run.envs[fake_run.calls.index(mysql)]
    assert env["MYSQL_PWD"] == "secret"


def test_start_timeout_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")

    class MysqlDown(FakeRun):
        def __call__(self, cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            self.returncode = 1 if "mysql" in cmd else 0
            return super().__call__(cmd, **kwargs)

    monkeypatch.setattr(infra, "_run", MysqlDown())
    ticks = iter(range(0, 10_000, 50))
    monkeypatch.setattr(infra.time, "monotonic", lambda: next(ticks))
    assert exit_code("start") == 1


def test_retry_gives_up_after_attempts(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    fake_run.returncode = 1
    with pytest.raises(infra.InfraError):
        infra._retry("x", ["cmd"])
    assert len(fake_run.calls) == infra.RETRY_ATTEMPTS


# --- stop -------------------------------------------------------------------


@pytest.mark.parametrize("stack", ["seaweedfs", "minio"])
def test_stop_touches_only_db_and_storage(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun, stack: str
) -> None:
    monkeypatch.setenv("STORAGE_STACK", stack)
    assert exit_code("stop") == 0
    services = ["db", "seaweedfs", "seaweedfs-bucket-init", "minio", "mc"]
    assert [c[-5:] for c in fake_run.calls] == [services]
    assert fake_run.calls[0][-6] == "stop"
    for call in fake_run.calls:
        assert "down" not in call
        assert "rm" not in call
        assert "otel-collector" not in call
        assert "--profile" in call


# --- status -----------------------------------------------------------------


def test_status_running(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "minio")
    monkeypatch.setattr(infra, "_run", FakeRun(running="db\nminio\notel-collector\n"))
    assert exit_code("status") == 0
    out = capsys.readouterr()
    assert "minio: running" in out.out


def test_status_ignores_init_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra, "_run", FakeRun(running="db\nseaweedfs\n"))
    assert exit_code("status") == 0


@pytest.mark.parametrize("running", ["", "db\n", "seaweedfs\n", "db\nminio\n"])
def test_status_stopped_or_partial_exits_3(
    monkeypatch: pytest.MonkeyPatch, running: str
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra, "_run", FakeRun(running=running))
    assert exit_code("status") == 3


@pytest.mark.parametrize("value", [None, "", "nope"])
def test_status_without_valid_stack_exits_4(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun, value: str | None
) -> None:
    if value is not None:
        monkeypatch.setenv("STORAGE_STACK", value)
    assert exit_code("status") == 4


def test_status_docker_failure_exits_4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra, "_run", FakeRun(returncode=1))
    assert exit_code("status") == 4


def test_status_without_docker_exits_4(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra.shutil, "which", lambda _: None)
    assert exit_code("status") == 4


def test_infra_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(infra.__file__).read_text())
    modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert modules <= set(sys.stdlib_module_names)


def test_start_fails_when_init_service_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setattr(infra, "_host_port_ready", lambda: True)
    monkeypatch.setattr(infra, "_run", FakeRun(init_exit=1))
    assert exit_code("start") == 1


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("localhost", ("localhost", 3306)),
        ("127.0.0.1:3307", ("127.0.0.1", 3307)),
    ],
)
def test_db_host_address(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: tuple[str, int]
) -> None:
    monkeypatch.setenv("DB_HOST", value)
    assert infra._db_host_address() == expected


def test_start_with_invalid_db_host_port_exits_6(
    monkeypatch: pytest.MonkeyPatch, fake_run: FakeRun
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "seaweedfs")
    monkeypatch.setenv("DB_HOST", "localhost:abc")
    assert exit_code("start") == 6
    assert fake_run.calls == []
