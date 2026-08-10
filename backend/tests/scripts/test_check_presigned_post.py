import pytest

from scripts.check_presigned_post import (
    RoundResult,
    TransferResult,
    percentile,
    summarize_rounds,
)


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
