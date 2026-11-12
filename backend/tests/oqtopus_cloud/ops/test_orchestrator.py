"""Orchestrator: ordered, idempotent (skip done), resumable, fail-closed."""

import pytest

from oqtopus_cloud.ops.journal import OperationJournal
from oqtopus_cloud.ops.orchestrator import OperationFailed, run


def _journal(tmp_path):
    return OperationJournal(str(tmp_path / "journal"))


def test_all_steps_run_in_order(tmp_path):
    j = _journal(tmp_path)
    calls = []
    op = j.create("cmd", "t", ["a", "b", "c"])
    run(j, op, {n: (lambda n=n: calls.append(n)) for n in ("a", "b", "c")})
    assert calls == ["a", "b", "c"]
    assert j.load(op.operation_id).status == "done"


def test_failure_stops_and_exits_nonzero(tmp_path):
    j = _journal(tmp_path)
    calls = []

    def boom():
        raise RuntimeError("nope")

    op = j.create("cmd", "t", ["a", "b", "c"])
    fns = {"a": lambda: calls.append("a"), "b": boom, "c": lambda: calls.append("c")}
    with pytest.raises(OperationFailed):
        run(j, op, fns)
    # b failed -> c never ran (fail-closed: no later step runs).
    assert calls == ["a"]
    loaded = j.load(op.operation_id)
    assert loaded.status == "failed"
    assert loaded.step("a").status == "done"
    assert loaded.step("b").status == "failed"
    assert loaded.step("c").status == "pending"


def test_resume_skips_done_and_is_idempotent(tmp_path):
    j = _journal(tmp_path)
    calls = []

    def flaky():
        calls.append("b")
        if len([c for c in calls if c == "b"]) == 1:
            raise RuntimeError("first attempt fails")

    op = j.create("cmd", "t", ["a", "b", "c"])
    fns = {"a": lambda: calls.append("a"), "b": flaky, "c": lambda: calls.append("c")}
    with pytest.raises(OperationFailed):
        run(j, op, fns)
    assert calls == ["a", "b"]

    # Resume with the same operation_id: 'a' is skipped (done), 'b' retried, 'c' runs.
    op2 = j.load(op.operation_id)
    run(j, op2, fns)
    assert calls == ["a", "b", "b", "c"]  # 'a' not re-run
    assert j.load(op.operation_id).status == "done"


def test_missing_step_callable_is_rejected(tmp_path):
    j = _journal(tmp_path)
    op = j.create("cmd", "t", ["a", "b"])
    with pytest.raises(KeyError):
        run(j, op, {"a": lambda: None})  # no 'b'
