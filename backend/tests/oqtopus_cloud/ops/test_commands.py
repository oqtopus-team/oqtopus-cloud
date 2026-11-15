"""Command step sequences: preflight identity, order (fail-closed), idempotency."""

import pytest

from oqtopus_cloud.ops import commands
from oqtopus_cloud.ops.journal import OperationJournal
from oqtopus_cloud.ops.orchestrator import OperationFailed, run


class FakeLdap:
    def __init__(self, log, by_uid=None, by_mail=None):
        self.log = log
        self.by_uid = by_uid
        self.by_mail = by_mail

    def find_user(self, uid):
        self.log.append(("ldap", "find_user", uid))
        return self.by_uid

    def find_by_mail(self, mail):
        self.log.append(("ldap", "find_by_mail", mail))
        return self.by_mail

    def create_user(self, uid, mail, cn, sn, given_name):
        self.log.append(("ldap", "create_user", uid))

    def set_temp_password(self, uid, temp_password):  # password NOT logged
        self.log.append(("ldap", "set_temp_password", uid))

    def add_to_admin_group(self, uid):
        self.log.append(("ldap", "add_to_admin_group", uid))

    def remove_from_admin_group(self, uid):
        self.log.append(("ldap", "remove_from_admin_group", uid))

    def disable_account(self, uid):
        self.log.append(("ldap", "disable_account", uid))


class FakeKc:
    def __init__(self, log):
        self.log = log

    def revoke_sessions(self, username):
        self.log.append(("kc", "revoke_sessions", username))


class FakeDb:
    def __init__(self, log, exists=True):
        self.log = log
        self.exists = exists

    def user_exists(self, email):
        self.log.append(("db", "user_exists", email))
        return self.exists

    def suspend(self, email):
        self.log.append(("db", "suspend", email))

    def revoke_api_token(self, email):
        self.log.append(("db", "revoke_api_token", email))


def _run(tmp_path, command, steps):
    j = OperationJournal(str(tmp_path / "j"))
    op = j.create(command, "t", list(steps))
    run(j, op, steps)


def _methods(log):
    return [m for _, m, _ in log]


def test_user_disable_preflights_then_suspends_db_first(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "demo@x"})
    steps = commands.user_disable_steps(
        ldap, FakeKc(log), FakeDb(log), uid="demo", email="demo@x"
    )
    _run(tmp_path, "user-disable", steps)
    assert _methods(log) == [
        "find_user",      # preflight (read-only, identity check)
        "suspend",        # first mutation = DB
        "revoke_api_token",
        "revoke_sessions",
        "remove_from_admin_group",
        "disable_account",
    ]


def test_user_disable_rejects_uid_email_mismatch_before_mutation(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "someone-else@x"})
    steps = commands.user_disable_steps(
        ldap, FakeKc(log), FakeDb(log), uid="demo", email="demo@x"
    )
    with pytest.raises(OperationFailed):
        _run(tmp_path, "user-disable", steps)
    assert ("db", "suspend", "demo@x") not in log  # no mutation happened


def test_user_disable_continues_when_no_db_row(tmp_path):
    # A never-logged-in user has no DB row yet. That is "already inaccessible in
    # the DB", not an error: deactivation still proceeds (db_suspend no-ops).
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "demo@x"})
    steps = commands.user_disable_steps(
        ldap, FakeKc(log), FakeDb(log, exists=False), uid="demo", email="demo@x"
    )
    _run(tmp_path, "user-disable", steps)  # no raise
    assert ("ldap", "disable_account", "demo") in log
    assert log[0] == ("ldap", "find_user", "demo")  # read-only preflight first
    assert log[1] == ("db", "suspend", "demo@x")  # DB first among mutations


def test_user_delete_is_logical_same_as_disable(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "demo@x"})
    steps = commands.user_delete_steps(
        ldap, FakeKc(log), FakeDb(log), uid="demo", email="demo@x"
    )
    _run(tmp_path, "user-delete", steps)
    assert ("ldap", "disable_account", "demo") in log  # no physical delete


def test_admin_revoke_removes_group_before_revoking_sessions(tmp_path):
    log = []
    steps = commands.admin_revoke_steps(FakeLdap(log), FakeKc(log), uid="demo")
    _run(tmp_path, "admin-revoke", steps)
    assert _methods(log) == ["remove_from_admin_group", "revoke_sessions"]


def test_admin_grant_preflights_then_adds_group_then_revokes_sessions(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "demo@x"})
    steps = commands.admin_grant_steps(ldap, FakeKc(log), uid="demo")
    _run(tmp_path, "admin-grant", steps)
    assert _methods(log) == ["find_user", "add_to_admin_group", "revoke_sessions"]


def test_admin_grant_rejects_unknown_uid(tmp_path):
    log = []
    steps = commands.admin_grant_steps(FakeLdap(log, by_uid=None), FakeKc(log), uid="ghost")
    with pytest.raises(OperationFailed):
        _run(tmp_path, "admin-grant", steps)
    assert ("ldap", "add_to_admin_group", "ghost") not in log


def test_user_add_rejects_existing_uid(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid={"uid": "demo", "mail": "demo@x"})
    steps = commands.user_add_steps(
        ldap, uid="demo", email="demo@x", cn="c", sn="s", given_name="g", temp_password="t"
    )
    with pytest.raises(OperationFailed):
        _run(tmp_path, "user-add", steps)
    assert ("ldap", "set_temp_password", "demo") not in log  # no password reset


def test_user_add_rejects_email_in_use_by_other_entry(tmp_path):
    log = []
    ldap = FakeLdap(log, by_uid=None, by_mail={"uid": "other", "mail": "demo@x"})
    steps = commands.user_add_steps(
        ldap, uid="demo", email="demo@x", cn="c", sn="s", given_name="g", temp_password="t"
    )
    with pytest.raises(OperationFailed):
        _run(tmp_path, "user-add", steps)
    assert ("ldap", "create_user", "demo") not in log


def test_user_add_creates_when_absent(tmp_path):
    log = []
    steps = commands.user_add_steps(
        FakeLdap(log, by_uid=None, by_mail=None), uid="demo", email="demo@x",
        cn="c", sn="s", given_name="g", temp_password="t",
    )
    _run(tmp_path, "user-add", steps)
    assert ("ldap", "create_user", "demo") in log
    assert ("ldap", "set_temp_password", "demo") in log
