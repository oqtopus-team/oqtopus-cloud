"""Start, stop and inspect the local DB and object storage.

Usage: ``oqtopus-cloud-infra <start|stop|status>``

The DB and the storage are handled as one unit: job payloads and
``device_info`` live only in the storage while the DB rows refer to them, and
both are seeded from the same dataset.

``STORAGE_STACK`` selects the storage stack (see ``STACKS``). There is no
default here: the caller (the Makefile, oqtopus-cli) decides. Settings such as
credentials and endpoints are exported by the caller; this module only knows
the structure of each stack.

Exit codes follow the LSB init-script conventions:

=============  =====  =====================================================
subcommand     code   meaning
=============  =====  =====================================================
start / stop   0      success (``start`` when running, ``stop`` when stopped)
start / stop   1      generic error, including a timeout while waiting
any            2      invalid arguments
start / stop   5      a required program (docker) is missing
start / stop   6      missing configuration (``STORAGE_STACK``, ``DB_*``)
status         0      running: the DB and the stack's main service are up
status         3      stopped (including partially running)
status         4      status unknown (docker unusable, invalid configuration)
=============  =====  =====================================================

Logs go to stderr; stdout is used only for the ``status`` output, whose format
is not part of the contract.

The command name ``oqtopus-cloud-infra`` is depended on by oqtopus-cli.
Renaming it is a breaking change.

Call it after ``uv sync --no-dev`` with ``uv run --no-sync oqtopus-cloud-infra``.

This module deliberately uses the standard library only and imports nothing
from the application, so that it also works where the application's
dependencies are not importable.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_STOPPED = 3  # status only
EXIT_UNKNOWN = 4  # status only
EXIT_MISSING_PROGRAM = 5
EXIT_NOT_CONFIGURED = 6

BACKEND_DIR = Path(__file__).resolve().parents[1]

DB_SERVICE = "db"
MYSQL_DEFAULT_PORT = 3306

MYSQL_TIMEOUT_S = 120
HOST_PORT_TIMEOUT_S = 60
INIT_SERVICE_TIMEOUT_S = 120
RETRY_ATTEMPTS = 10
RETRY_INTERVAL_S = 3
POLL_INTERVAL_S = 2


@dataclass(frozen=True)
class Stack:
    driver: str  # value of STORAGE_DRIVER
    service: str  # main service
    init_service: str  # one-shot service that creates the bucket
    profile: str | None  # compose profile, if any


STACKS: dict[str, Stack] = {
    "seaweedfs": Stack("seaweedfs", "seaweedfs", "seaweedfs-bucket-init", None),
    "minio": Stack("local:minio", "minio", "mc", "minio"),
}


class InfraError(Exception):
    """A failure that ends the command with ``code``."""

    def __init__(self, message: str, code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.code = code


class ConfigError(InfraError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_NOT_CONFIGURED)


def resolve_stack() -> tuple[str, Stack]:
    """Return the stack selected by ``STORAGE_STACK``.

    An empty value is treated as unset (GNU make exports an empty string for an
    undefined variable).
    """
    name = os.environ.get("STORAGE_STACK", "")
    if name == "":
        raise ConfigError(f"STORAGE_STACK must be set (one of: {', '.join(STACKS)})")
    if name not in STACKS:
        raise ConfigError(
            f"unknown STORAGE_STACK {name!r} (one of: {', '.join(STACKS)})"
        )
    return name, STACKS[name]


def apply_stack_env() -> str | None:
    """Set ``STORAGE_DRIVER`` from ``STORAGE_STACK``, overwriting any value.

    Does nothing and returns None when ``STORAGE_STACK`` is unset or empty, so
    that uses unrelated to a stack are not affected.
    """
    if os.environ.get("STORAGE_STACK", "") == "":
        return None
    name, stack = resolve_stack()
    os.environ["STORAGE_DRIVER"] = stack.driver
    return name


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise InfraError("docker is not installed or not on PATH", EXIT_MISSING_PROGRAM)


def _require_compose_file() -> None:
    if not (BACKEND_DIR / "compose.yaml").is_file():
        raise InfraError(f"compose.yaml not found in {BACKEND_DIR}")


def _compose(*args: str) -> list[str]:
    cmd = ["docker", "compose"]
    for profile in sorted({s.profile for s in STACKS.values() if s.profile}):
        cmd += ["--profile", profile]
    return [*cmd, *args]


def _run(
    cmd: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command in ``backend/``; its stdout goes to stderr unless captured."""
    return subprocess.run(
        list(cmd),
        cwd=BACKEND_DIR,
        env=None if env is None else dict(env),
        timeout=timeout,
        text=True,
        stdout=subprocess.PIPE if capture else sys.stderr,
        stderr=subprocess.PIPE if capture else sys.stderr,
        check=False,
    )


def _check(cmd: Sequence[str], **kwargs: object) -> None:
    try:
        result = _run(cmd, **kwargs)  # type: ignore[arg-type]
    except subprocess.TimeoutExpired as error:
        raise InfraError(f"timed out: {' '.join(cmd)}") from error
    if result.returncode != 0:
        raise InfraError(f"failed (exit {result.returncode}): {' '.join(cmd)}")


def _retry(description: str, cmd: Sequence[str]) -> None:
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            _check(cmd)
            return
        except InfraError as error:
            if attempt == RETRY_ATTEMPTS:
                raise InfraError(f"{description} did not succeed: {error}") from error
            _log(f"{description} failed (attempt {attempt}), retrying...")
            time.sleep(RETRY_INTERVAL_S)


def _wait(description: str, timeout_s: float, probe: Callable[[], bool]) -> None:
    deadline = time.monotonic() + timeout_s
    while not probe():
        if time.monotonic() >= deadline:
            raise InfraError(f"timed out waiting for {description}")
        time.sleep(POLL_INTERVAL_S)


def _db_settings() -> tuple[str, str, str]:
    missing = [
        k
        for k in ("DB_HOST", "DB_NAME", "DB_USERNAME", "DB_PASSWORD")
        if not os.environ.get(k)
    ]
    if missing:
        raise ConfigError(f"missing environment variable(s): {', '.join(missing)}")
    env = os.environ
    return env["DB_NAME"], env["DB_USERNAME"], env["DB_PASSWORD"]


def _mysql_ready(name: str, user: str, password: str) -> bool:
    # Probe over TCP (-h127.0.0.1 --protocol=tcp), not the unix socket: on a
    # fresh volume MySQL first runs a socket-only temporary server for init,
    # and a socket probe passes during that phase, after which Alembic's TCP
    # connect hits the server mid-restart ("Lost connection", 2013).
    # `-e MYSQL_PWD` (no value) passes the password through the environment so
    # that it does not appear in the process arguments.
    cmd = _compose(
        "exec", "-T", "-e", "MYSQL_PWD", DB_SERVICE,
        "mysql", "-h127.0.0.1", "--protocol=tcp", f"-u{user}", name,
        "-e", "SELECT 1",
    )  # fmt: skip
    env = {**os.environ, "MYSQL_PWD": password}
    try:
        result = _run(cmd, env=env, timeout=30, capture=True)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _db_host_address() -> tuple[str, int]:
    """Return the host and port of ``DB_HOST``, the address Alembic connects to.

    ``DB_HOST`` is put into the DB URL as is, so it may carry a port
    (``host:port``); otherwise MySQL's default port is used.
    """
    host, _, port = os.environ["DB_HOST"].partition(":")
    try:
        return host, int(port) if port else MYSQL_DEFAULT_PORT
    except ValueError as error:
        raise ConfigError(
            f"invalid port in DB_HOST: {os.environ['DB_HOST']!r}"
        ) from error


def _host_port_ready() -> bool:
    # With Docker Desktop / WSL2 the published port can lag behind the
    # container, so check that the host side actually accepts connections,
    # at the address the host-side clients (Alembic, seed) will use.
    try:
        with socket.create_connection(_db_host_address(), timeout=2):
            return True
    except OSError:
        return False


def _running_services() -> set[str]:
    result = _run(_compose("ps", "--status", "running", "--services"), capture=True)
    if result.returncode != 0:
        raise InfraError(
            result.stderr.strip() or "docker compose ps failed", EXIT_UNKNOWN
        )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _init_service_finished(service: str) -> bool:
    """Return True once the one-shot ``service`` has exited with code 0.

    ``docker compose wait`` cannot be used: it fails with "no containers" for a
    container that has already exited, which is the usual case here.
    """
    result = _run(_compose("ps", "-a", "--format", "json", service), capture=True)
    if result.returncode != 0:
        raise InfraError(result.stderr.strip() or f"docker compose ps {service} failed")
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        info = json.loads(line)
        if info.get("State") in ("exited", "dead"):
            if info.get("ExitCode") != 0:
                raise InfraError(f"{service} exited with code {info.get('ExitCode')}")
            return True
    return False


def cmd_start() -> int:
    name, stack = resolve_stack()
    db_name, db_user, db_password = _db_settings()
    _db_host_address()  # fail early on an invalid DB_HOST
    _require_docker()
    _require_compose_file()
    os.environ["STORAGE_DRIVER"] = stack.driver

    # Stacks can publish the same host ports (SeaweedFS and MinIO both use
    # 9001): stop the others so the stack can be switched without `stop`.
    others = [
        svc
        for other_name, other in STACKS.items()
        if other_name != name
        for svc in (other.service, other.init_service)
    ]
    if others:
        _log(f"Stopping the other stacks' services: {' '.join(others)}")
        _check(_compose("stop", *others))

    _log(f"Starting {DB_SERVICE} and storage stack '{name}'...")
    _check(_compose("up", "-d", DB_SERVICE, stack.service, stack.init_service))

    _log("Waiting for MySQL to be ready...")
    _wait("MySQL", MYSQL_TIMEOUT_S, lambda: _mysql_ready(db_name, db_user, db_password))
    _log("Waiting for MySQL on the host port...")
    _wait("MySQL on the host port", HOST_PORT_TIMEOUT_S, _host_port_ready)

    _log("Applying migrations...")
    _retry("alembic upgrade", [sys.executable, "-m", "alembic", "upgrade", "head"])
    _log("Seeding the DB...")
    _retry("DB seed", [sys.executable, "scripts/seed.py"])

    # The bucket is created by a one-shot service, and `up -d` returns without
    # waiting for it. Seeding storage before it finishes would write into a
    # bucket that does not exist yet, so wait for it to exit first.
    _log("Waiting for the bucket initialization...")
    _wait(
        stack.init_service,
        INIT_SERVICE_TIMEOUT_S,
        lambda: _init_service_finished(stack.init_service),
    )
    if (BACKEND_DIR / "storage" / "init_storage.py").is_file():
        _log("Seeding the storage...")
        _check([sys.executable, "storage/init_storage.py"])

    _log("Ready.")
    return EXIT_OK


def cmd_stop() -> int:
    resolve_stack()
    _require_docker()
    _require_compose_file()
    services = [DB_SERVICE]
    for stack in STACKS.values():
        services += [stack.service, stack.init_service]
    # Neither `down` nor `rm`: `down` would also remove the network and the other
    # containers of the project, and the containers are kept so that `start`
    # resumes them. Data lives in volumes (see `volumes` in compose.yaml).
    _check(_compose("stop", *services))
    return EXIT_OK


def cmd_status() -> int:
    try:
        _, stack = resolve_stack()
    except ConfigError as error:
        raise InfraError(str(error), EXIT_UNKNOWN) from error
    try:
        _require_docker()
        _require_compose_file()
    except InfraError as error:
        raise InfraError(str(error), EXIT_UNKNOWN) from error
    try:
        running = _running_services()
    except (OSError, subprocess.SubprocessError) as error:
        raise InfraError(str(error), EXIT_UNKNOWN) from error

    # The init services run once and exit, so they are not part of the status.
    wanted = [DB_SERVICE, stack.service]
    for svc in wanted:
        print(f"{svc}: {'running' if svc in running else 'stopped'}")
    return EXIT_OK if all(svc in running for svc in wanted) else EXIT_STOPPED


_COMMANDS = {"start": cmd_start, "stop": cmd_stop, "status": cmd_status}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="oqtopus-cloud-infra",
        description="Start, stop and inspect the local DB and object storage.",
    )
    parser.add_argument("command", choices=sorted(_COMMANDS))
    args = parser.parse_args(argv)  # exits with 2 on invalid arguments
    try:
        code = _COMMANDS[args.command]()
    except InfraError as error:
        _log(f"oqtopus-cloud-infra: {error}")
        code = error.code
    sys.exit(code)
