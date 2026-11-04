"""Operation journal: create, persist, mark, resume."""

from oqtopus_cloud.ops.journal import OperationJournal


def test_create_persists_pending_steps(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create("user-disable", "demo", ["a", "b"])
    loaded = j.load(op.operation_id)
    assert loaded.command == "user-disable"
    assert loaded.target == "demo"
    assert [s.status for s in loaded.steps] == ["pending", "pending"]
    assert loaded.status == "running"


def test_mark_and_reload(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create("c", "t", ["a", "b"])
    j.mark(op, "a", "done")
    j.mark(op, "b", "failed", "boom")
    loaded = j.load(op.operation_id)
    assert loaded.step("a").status == "done"
    assert loaded.step("b").status == "failed"
    assert loaded.step("b").detail == "boom"


def test_resume_point_is_first_non_done(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create("c", "t", ["a", "b", "c"])
    j.mark(op, "a", "done")
    loaded = j.load(op.operation_id)
    first_pending = next(s.name for s in loaded.steps if s.status != "done")
    assert first_pending == "b"


def test_inputs_are_persisted(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create("user-disable", "demo", ["a"], {"uid": "demo", "email": "d@x"})
    assert j.load(op.operation_id).inputs == {"uid": "demo", "email": "d@x"}


def test_invalid_operation_id_is_rejected(tmp_path):
    import pytest

    j = OperationJournal(str(tmp_path / "j"))
    for bad in ("../etc/passwd", "not-a-uuid", "../../x"):
        with pytest.raises(ValueError):
            j.load(bad)


def test_journal_dir_is_0700(tmp_path):
    import os
    import stat

    d = tmp_path / "j"
    OperationJournal(str(d))
    assert stat.S_IMODE(os.stat(d).st_mode) == 0o700
