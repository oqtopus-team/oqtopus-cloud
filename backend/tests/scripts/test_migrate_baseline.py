import pytest

from scripts import migrate_baseline


def test_alembic_ini_is_resolved() -> None:
    assert migrate_baseline.ALEMBIC_INI.is_file()


def test_baseline_is_the_root_of_the_chain() -> None:
    config = migrate_baseline._config()
    revision = migrate_baseline.baseline_revision(config)

    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(config)
    assert revision
    # The baseline must be the root, not a head: stamping a head would mark the
    # revisions in between as applied without ever running their DDL.
    assert script.get_revision(revision).down_revision is None
    assert revision not in script.get_heads() or len(list(script.walk_revisions())) == 1


def test_refuses_to_stamp_an_already_tracked_database(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(migrate_baseline, "current_revision", lambda: "676e54a5dbaf")
    stamped: list[str] = []
    monkeypatch.setattr(
        migrate_baseline.command,
        "stamp",
        lambda config, revision: stamped.append(revision),
    )

    assert migrate_baseline.main() == 1
    assert stamped == []
    assert "Refusing to stamp" in capsys.readouterr().err


def test_stamps_the_baseline_when_untracked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(migrate_baseline, "current_revision", lambda: "")
    stamped: list[str] = []
    monkeypatch.setattr(
        migrate_baseline.command,
        "stamp",
        lambda config, revision: stamped.append(revision),
    )

    assert migrate_baseline.main() == 0
    assert stamped == [migrate_baseline.baseline_revision(migrate_baseline._config())]
    assert "no DDL will run" in capsys.readouterr().out
