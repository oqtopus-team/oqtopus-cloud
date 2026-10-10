import pytest

from oqtopus_cloud.worker.pending_jobs_updater import local_scheduler


class _Stop(Exception):
    pass


def _stop(_: float) -> None:
    raise _Stop


def test_main_applies_storage_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_STACK", "minio")
    monkeypatch.setenv("STORAGE_DRIVER", "seaweedfs")
    monkeypatch.setattr(local_scheduler, "sleep", _stop)
    monkeypatch.setattr(
        "oqtopus_cloud.worker.pending_jobs_updater.lambda_function.lambda_handler",
        lambda event, context: None,
    )
    with pytest.raises(_Stop):
        local_scheduler.main()
    assert local_scheduler.os.environ["STORAGE_DRIVER"] == "local:minio"


def test_main_without_storage_stack_leaves_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STORAGE_STACK", raising=False)
    monkeypatch.setenv("STORAGE_DRIVER", "s3")
    monkeypatch.setattr(local_scheduler, "sleep", _stop)
    monkeypatch.setattr(
        "oqtopus_cloud.worker.pending_jobs_updater.lambda_function.lambda_handler",
        lambda event, context: None,
    )
    with pytest.raises(_Stop):
        local_scheduler.main()
    assert local_scheduler.os.environ["STORAGE_DRIVER"] == "s3"


def test_main_with_unknown_storage_stack_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STORAGE_STACK", "nope")
    with pytest.raises(SystemExit):
        local_scheduler.main()
