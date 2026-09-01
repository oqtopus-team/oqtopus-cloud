import argparse

import pytest

from scripts.check_presigned_post import (
    RoundResult,
    run,
    TransferResult,
    create_round_result,
    ensure_transfers_succeeded,
    percentile,
    succeeded,
    summarize_rounds,
    validate_args,
)


def make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "count": 1,
        "workers": 1,
        "payload_bytes": 1,
        "timeout": 30.0,
        "rounds": 1,
        "warmup_rounds": 0,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def make_round(
    operation: str,
    *,
    warmup: bool,
    requests: int,
    elapsed_seconds: float,
) -> RoundResult:
    return RoundResult(
        operation=operation,
        round_number=1,
        warmup=warmup,
        requests=requests,
        errors=0,
        elapsed_seconds=elapsed_seconds,
        operations_per_second=requests / elapsed_seconds,
        mebibytes_per_second=0,
        latency_p50_ms=0,
        latency_p95_ms=0,
        latency_p99_ms=0,
    )


def test_percentile_interpolates_values() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert percentile(values, 0.50) == pytest.approx(2.5)
    assert percentile(values, 0.95) == pytest.approx(3.85)


def test_summarize_rounds_filters_operation_and_warmup() -> None:
    rounds = [
        make_round("POST", warmup=True, requests=100, elapsed_seconds=1),
        make_round("POST", warmup=False, requests=10, elapsed_seconds=2),
        make_round("GET", warmup=False, requests=20, elapsed_seconds=1),
    ]
    samples = [TransferResult("key", 204, 0.001)] * 10

    summary = summarize_rounds("POST", rounds, samples, payload_bytes=1024)

    assert summary["rounds"] == 1
    assert summary["requests"] == 10
    assert summary["operations_per_second"] == pytest.approx(5)
    assert summary["mebibytes_per_second"] == pytest.approx(10 / 1024 / 2)


@pytest.mark.parametrize(
    "overrides",
    [
        {"count": 0},
        {"workers": 0},
        {"payload_bytes": 0},
        {"timeout": 0},
        {"rounds": 0},
        {"warmup_rounds": -1},
    ],
)
def test_validate_args_rejects_out_of_range_values(overrides) -> None:
    with pytest.raises(ValueError):
        validate_args(make_args(**overrides))


def test_validate_args_accepts_defaults() -> None:
    validate_args(make_args())


@pytest.mark.parametrize(
    ("operation", "status", "content_matches", "expected"),
    [
        ("POST", 204, True, True),
        ("POST", 200, True, True),
        ("POST", 403, True, False),
        ("GET", 200, True, True),
        # A presigned POST answers 204, but that is a failure for a GET.
        ("GET", 204, True, False),
        # Right status, wrong bytes: the object came back corrupted.
        ("GET", 200, False, False),
    ],
)
def test_succeeded(operation, status, content_matches, expected) -> None:
    result = TransferResult("key", status, 0.1, content_matches=content_matches)

    assert succeeded(operation, result) is expected


def test_ensure_transfers_succeeded_reports_the_failures() -> None:
    results = [
        TransferResult("ok", 204, 0.1),
        TransferResult("denied", 403, 0.1),
    ]

    with pytest.raises(RuntimeError, match="POST failures"):
        ensure_transfers_succeeded("POST", results)


def test_ensure_transfers_succeeded_passes_when_all_succeed() -> None:
    ensure_transfers_succeeded("POST", [TransferResult("ok", 204, 0.1)])


def test_create_round_result_counts_errors() -> None:
    results = [
        TransferResult("ok", 200, 0.1),
        TransferResult("bad-status", 500, 0.2),
        TransferResult("corrupt", 200, 0.3, content_matches=False),
    ]

    round_result = create_round_result(
        "GET",
        round_number=2,
        warmup=False,
        results=results,
        elapsed_seconds=1.5,
        payload_bytes=1024 * 1024,
    )

    assert round_result.requests == 3
    assert round_result.errors == 2
    assert round_result.operations_per_second == pytest.approx(2)
    assert round_result.mebibytes_per_second == pytest.approx(2)


MINIO_ENV = {
    "STORAGE_LOCAL_MINIO_BUCKET_NAME": "test-bucket",
    "STORAGE_LOCAL_MINIO_USERNAME": "minioadmin",
    "STORAGE_LOCAL_MINIO_PASSWORD": "minioadmin",
    "STORAGE_LOCAL_MINIO_ENDPOINT_URL": "http://localhost:9000",
}


@pytest.mark.parametrize("driver", ["seaweedfs", "local:minio"])
def test_run_accepts_the_self_hosted_drivers(monkeypatch, driver) -> None:
    """
    Both self-hosted drivers are checkable: `local:minio` is deprecated, but it
    stays runnable so its behaviour can be compared against seaweedfs
    """

    checked = []
    monkeypatch.setenv("STORAGE_DRIVER", driver)
    for name, value in MINIO_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr("scripts.check_presigned_post.get_storage", lambda: "storage")
    monkeypatch.setattr(
        "scripts.check_presigned_post.run_check",
        lambda args, storage: checked.append(storage),
    )

    run(make_args(benchmark=False))

    assert checked == ["storage"]


def test_run_rejects_the_s3_driver(monkeypatch) -> None:
    """
    The check writes and deletes objects, so it must never target real S3
    """

    monkeypatch.setenv("STORAGE_DRIVER", "s3")

    with pytest.raises(RuntimeError, match="production S3"):
        run(make_args(benchmark=False))


def test_run_rejects_an_incomplete_local_minio_configuration(monkeypatch) -> None:
    """
    The deprecated driver reads its settings leniently, so a missing endpoint
    would send these uploads and deletes to real S3
    """

    monkeypatch.setenv("STORAGE_DRIVER", "local:minio")
    for name, value in MINIO_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("STORAGE_LOCAL_MINIO_ENDPOINT_URL")

    with pytest.raises(RuntimeError, match="STORAGE_LOCAL_MINIO_ENDPOINT_URL"):
        run(make_args(benchmark=False))
