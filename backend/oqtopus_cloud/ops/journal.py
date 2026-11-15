"""Persistent operation journal for the ops orchestrator.

Each operation is a JSON file ``<journal_dir>/<operation_id>.json`` recording the
command, target, the immutable non-secret ``inputs`` the operation was created
with, and the status of every step (``pending`` / ``done`` / ``failed``). A
re-run loads the journal and resumes from the first non-``done`` step; the CLI
rejects a resume whose inputs do not match (so pending steps cannot run against a
different target). The journal never stores secrets, passwords, or raw exception
text.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from typing import Literal

StepStatus = Literal["pending", "done", "failed"]
OpStatus = Literal["running", "done", "failed"]


@dataclass
class Step:
    name: str
    status: StepStatus = "pending"
    detail: str = ""  # a non-secret note (e.g. the failed step's exception TYPE)


@dataclass
class Operation:
    operation_id: str
    command: str
    target: str
    inputs: dict = field(default_factory=dict)  # immutable, non-secret
    steps: list[Step] = field(default_factory=list)
    status: OpStatus = "running"

    def step(self, name: str) -> Step:
        for s in self.steps:
            if s.name == name:
                return s
        raise KeyError(name)

    def step_names(self) -> list[str]:
        return [s.name for s in self.steps]


def _validate_operation_id(operation_id: str) -> str:
    # Must be a UUID; this both pins the format and blocks path traversal.
    return str(uuid.UUID(str(operation_id)))


class OperationJournal:
    """File-backed store of :class:`Operation` records (dir 0700, files 0600)."""

    def __init__(self, journal_dir: str):
        self._dir = journal_dir
        os.makedirs(self._dir, mode=0o700, exist_ok=True)
        try:
            os.chmod(self._dir, 0o700)
        except OSError:
            pass

    def _path(self, operation_id: str) -> str:
        return os.path.join(self._dir, f"{_validate_operation_id(operation_id)}.json")

    def lock_path(self, operation_id: str) -> str:
        return os.path.join(self._dir, f"{_validate_operation_id(operation_id)}.lock")

    def create(
        self,
        command: str,
        target: str,
        step_names: list[str],
        inputs: dict | None = None,
    ) -> Operation:
        op = Operation(
            operation_id=str(uuid.uuid4()),
            command=command,
            target=target,
            inputs=dict(inputs or {}),
            steps=[Step(name=n) for n in step_names],
        )
        self.save(op)
        return op

    def load(self, operation_id: str) -> Operation:
        with open(self._path(operation_id), encoding="utf-8") as f:
            raw = json.load(f)
        raw["steps"] = [Step(**s) for s in raw.get("steps", [])]
        raw.setdefault("inputs", {})
        return Operation(**raw)

    def save(self, op: Operation) -> None:
        # Atomic 0600 write (tmp + rename) so a crash never leaves a half file.
        path = self._path(op.operation_id)
        tmp = f"{path}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(op), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def mark(
        self, op: Operation, step_name: str, status: StepStatus, detail: str = ""
    ) -> None:
        s = op.step(step_name)
        s.status = status
        s.detail = detail
        self.save(op)
