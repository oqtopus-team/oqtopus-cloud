"""CLI: resume binding (reject mismatched target) and temp-password file safety."""

import os

import pytest

from oqtopus_cloud.ops import cli
from oqtopus_cloud.ops.journal import OperationJournal


def test_resume_rejects_input_mismatch(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create("user-disable", "demo", ["a"], {"uid": "demo", "email": "d@x"})
    steps = {"a": lambda: None}
    # Same command and step names, but a DIFFERENT target -> refuse to resume.
    with pytest.raises(SystemExit) as ei:
        cli._run(j, "user-disable", "demo", steps, {"uid": "other", "email": "o@x"}, op.operation_id)
    assert ei.value.code == 2


def test_resume_rejects_deployment_or_endpoint_mismatch(tmp_path):
    # Same target but a different deployment / endpoint must not resume (a
    # dev-started operation cannot be applied to prod).
    j = OperationJournal(str(tmp_path / "j"))
    dev = {"uid": "demo", "deployment_id": "dev", "ldap_server": "ldaps://dev"}
    op = j.create("admin-revoke", "demo", ["a"], dev)
    prod = {"uid": "demo", "deployment_id": "prod", "ldap_server": "ldaps://prod"}
    with pytest.raises(SystemExit) as ei:
        cli._run(j, "admin-revoke", "demo", {"a": lambda: None}, prod, op.operation_id)
    assert ei.value.code == 2


def test_resume_accepts_matching_inputs(tmp_path):
    j = OperationJournal(str(tmp_path / "j"))
    inputs = {"uid": "demo", "email": "d@x"}
    op = j.create("user-disable", "demo", ["a"], inputs)
    ran = []
    cli._run(j, "user-disable", "demo", {"a": lambda: ran.append(1)}, inputs, op.operation_id)
    assert ran == [1]
    assert j.load(op.operation_id).status == "done"


def test_write_new_temp_password_is_0600_and_exclusive(tmp_path):
    p = tmp_path / "pw"
    pw = cli._write_new_temp_password(str(p))
    assert pw and p.read_text().strip() == pw
    assert oct(os.stat(p).st_mode & 0o777) == "0o600"
    # O_EXCL: a second call must not overwrite an existing file.
    with pytest.raises(FileExistsError):
        cli._write_new_temp_password(str(p))


def test_write_new_temp_password_refuses_symlink(tmp_path):
    real = tmp_path / "real"
    real.write_text("x")
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(OSError):
        cli._write_new_temp_password(str(link))
