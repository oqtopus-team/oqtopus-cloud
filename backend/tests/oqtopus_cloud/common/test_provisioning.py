"""First-login auto-provisioning (on-prem OIDC, Phase 1).

Exercises the identity-provisioning service and its wiring in
``_identity_via_cognito_sub`` against a real (sqlite) DB. Phase 1 keeps
``users.id = email`` and stores the IdP ``sub`` in ``users.cognito_id``.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Import so the patch targets (`_create_session`) exist on these modules.
import oqtopus_cloud.common.auth.authorization as authz
import oqtopus_cloud.common.auth.provisioning as provisioning
from oqtopus_cloud.common.auth.frontend import (
    AuthorizationError,
    _identity_via_cognito_sub,
)
from oqtopus_cloud.common.models.base import Base
from oqtopus_cloud.common.models.user import User, UserStatus


@pytest.fixture
def Local(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/prov.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def factory(read_timeout=None):
        return Session()

    monkeypatch.setattr(provisioning, "_create_session", factory)
    monkeypatch.setattr(authz, "_create_session", factory)
    monkeypatch.setenv("AUTH_ENFORCE_STATUS", "true")
    monkeypatch.setenv("OIDC_AUTO_PROVISION", "true")
    monkeypatch.setenv("OIDC_PRINCIPAL_CLAIM", "sub")
    yield Session
    engine.dispose()


def _seed(Session, *, id, email, cognito_id, status=UserStatus.approved):
    db = Session()
    db.add(User(id=id, email=email, cognito_id=cognito_id, userstatus=status))
    db.commit()
    db.close()


def _rows(Session):
    db = Session()
    try:
        return db.execute(select(User)).scalars().all()
    finally:
        db.close()


def _get(Session, cognito_id):
    db = Session()
    try:
        return db.execute(
            select(User).where(User.cognito_id == cognito_id)
        ).scalar()
    finally:
        db.close()


def test_first_login_creates_unapproved_and_403(Local):
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub({"sub": "s1", "email": "u@example.com"})
    rows = _rows(Local)
    assert len(rows) == 1
    assert rows[0].id == "u@example.com"
    assert rows[0].cognito_id == "s1"
    assert rows[0].userstatus == UserStatus.unapproved


def test_retry_same_jwt_no_duplicate_and_403(Local):
    claims = {"sub": "s1", "email": "u@example.com"}
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub(claims)
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub(claims)
    assert len(_rows(Local)) == 1


def test_after_approval_resolves(Local):
    claims = {"sub": "s1", "email": "u@example.com"}
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub(claims)
    # Admin approves.
    db = Local()
    row = db.execute(select(User).where(User.cognito_id == "s1")).scalar()
    row.userstatus = UserStatus.approved
    db.commit()
    db.close()
    identity = _identity_via_cognito_sub(claims)
    assert identity.user_id == "u@example.com"
    assert identity.auth_method == "oidc"


def test_missing_email_claim_creates_no_row(Local):
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub({"sub": "s2"})  # no email
    assert len(_rows(Local)) == 0


def test_email_in_use_by_other_sub_is_403_no_change(Local):
    _seed(Local, id="u@example.com", email="u@example.com", cognito_id="s1")
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub({"sub": "s9", "email": "u@example.com"})
    rows = _rows(Local)
    assert len(rows) == 1
    assert rows[0].cognito_id == "s1"  # untouched


def test_same_sub_email_changed_is_403_no_change(Local):
    _seed(Local, id="u@example.com", email="u@example.com", cognito_id="s1")
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub({"sub": "s1", "email": "new@example.com"})
    row = _get(Local, "s1")
    assert row.id == "u@example.com"
    assert row.email == "u@example.com"  # not auto-updated


def test_provision_is_idempotent(Local):
    # Two provisioning calls for the same identity create exactly one row.
    provisioning.provision_oidc_user("s1", {"sub": "s1", "email": "u@example.com"})
    provisioning.provision_oidc_user("s1", {"sub": "s1", "email": "u@example.com"})
    assert len(_rows(Local)) == 1


def test_no_auto_provision_when_disabled(Local, monkeypatch):
    monkeypatch.setenv("OIDC_AUTO_PROVISION", "false")
    with pytest.raises(AuthorizationError):
        _identity_via_cognito_sub({"sub": "s1", "email": "u@example.com"})
    assert len(_rows(Local)) == 0  # AWS behavior: no row created


def test_integrity_error_recovery_branch(Local, monkeypatch):
    # Deterministically exercise the `except IntegrityError` recovery: a
    # "concurrent" session commits the same (sub, email) just before our commit,
    # so our commit hits the unique constraint. We must roll back, re-resolve,
    # treat the matching row as success, and leave exactly one row.
    sub, email = "s1", "u@example.com"
    state = {"injected": False}

    def factory(read_timeout=None):
        sess = Local()
        real_commit = sess.commit

        def commit_with_race():
            if not state["injected"]:
                state["injected"] = True
                other = Local()
                other.add(
                    User(
                        id=email,
                        email=email,
                        cognito_id=sub,
                        userstatus=UserStatus.unapproved,
                    )
                )
                other.commit()
                other.close()
            real_commit()

        monkeypatch.setattr(sess, "commit", commit_with_race)
        return sess

    monkeypatch.setattr(provisioning, "_create_session", factory)

    # Must not raise: the recovery path handles the race.
    provisioning.provision_oidc_user(sub, {"sub": sub, "email": email})
    assert state["injected"] is True  # the IntegrityError branch ran
    assert len(_rows(Local)) == 1
