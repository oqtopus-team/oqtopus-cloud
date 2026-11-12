"""The orchestrator runner: resumable, idempotent, fail-closed, single-writer.

A command is a list of named steps. :func:`run` executes them in order against
an :class:`~oqtopus_cloud.ops.journal.Operation`, skipping steps already
``done`` (so a re-run resumes from the first incomplete step). Each step
callable must be **idempotent**. On a step failure the journal records the
exception **type only** (never its raw message), the operation is marked
``failed``, and :class:`OperationFailed` is raised so the CLI exits non-zero -- a
partial failure is never reported as success.

A per-operation file lock prevents two processes from running the same
operation concurrently. Deactivation commands order their steps so the account
is disabled at the DB first; recovery only re-runs remaining disable steps
(never a re-grant), so a half-finished deactivation stays fail-closed.

The audit log records the operation id, command, target, and per-step status and
exception type -- never secrets, passwords, or raw exception text.
"""

from __future__ import annotations

import contextlib
import fcntl
import logging
import os
from collections.abc import Callable, Iterator

from oqtopus_cloud.ops.journal import Operation, OperationJournal

_audit = logging.getLogger("oqtopus_cloud.ops.audit")


class OperationFailed(Exception):
    """A step failed; the operation did not complete (CLI exits non-zero)."""


class OperationLocked(Exception):
    """Another process holds this operation's lock (concurrent run refused)."""


@contextlib.contextmanager
def _operation_lock(journal: OperationJournal, operation_id: str) -> Iterator[None]:
    path = journal.lock_path(operation_id)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            raise OperationLocked(
                f"operation {operation_id} is already running elsewhere"
            ) from e
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def run(
    journal: OperationJournal,
    op: Operation,
    step_fns: dict[str, Callable[[], None]],
) -> None:
    missing = [s.name for s in op.steps if s.name not in step_fns]
    if missing:
        raise KeyError(f"no callable for steps: {missing}")

    with _operation_lock(journal, op.operation_id):
        # Re-read under the lock so we never act on a state captured before
        # acquiring it (another process may have advanced it).
        op = journal.load(op.operation_id)
        _audit.info(
            "operation start id=%s command=%s target=%s",
            op.operation_id,
            op.command,
            op.target,
        )
        for step in op.steps:
            if step.status == "done":
                _audit.info(
                    "operation step skip (already done) id=%s step=%s",
                    op.operation_id,
                    step.name,
                )
                continue
            _audit.info("operation step start id=%s step=%s", op.operation_id, step.name)
            try:
                step_fns[step.name]()
            except Exception as e:  # noqa: BLE001 -- recorded (type only) and re-raised
                etype = type(e).__name__
                journal.mark(op, step.name, "failed", etype)
                op.status = "failed"
                journal.save(op)
                _audit.error(
                    "operation step FAILED id=%s step=%s error_type=%s",
                    op.operation_id,
                    step.name,
                    etype,
                )
                raise OperationFailed(
                    f"operation {op.operation_id} failed at step {step.name!r} "
                    f"(error type {etype})"
                ) from e
            journal.mark(op, step.name, "done")
            _audit.info("operation step done id=%s step=%s", op.operation_id, step.name)

        op.status = "done"
        journal.save(op)
        _audit.info("operation done id=%s command=%s", op.operation_id, op.command)
