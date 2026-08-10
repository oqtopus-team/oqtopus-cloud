#!/usr/bin/env python3
"""Exercise OQTOPUS presigned POST uploads against self-hosted storage."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import local
from time import perf_counter
from typing import Any, Callable, TypeVar
from uuid import uuid4

import requests  # type: ignore[import-untyped]

from oqtopus_cloud.common.storages import AbstractStorage, get_storage


@dataclass(frozen=True)
class UploadTarget:
    key: str
    url: str
    fields: dict[str, str]


@dataclass(frozen=True)
class DownloadTarget:
    key: str
    url: str


@dataclass(frozen=True)
class TransferResult:
    key: str
    status: int
    seconds: float
    content_matches: bool = True


@dataclass(frozen=True)
class RoundResult:
    operation: str
    round_number: int
    warmup: bool
    requests: int
    errors: int
    elapsed_seconds: float
    operations_per_second: float
    mebibytes_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float


_thread_state = local()
TransferTarget = TypeVar("TransferTarget")
# S3 implementations answer a presigned POST with 204 by default, or 200/201
# when the presigned policy asked for a different success status.
SUCCESSFUL_STATUSES = {"POST": (200, 201, 204), "GET": (200,)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload objects concurrently through OQTOPUS-generated presigned POSTs "
            "and verify every object in storage."
        )
    )
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--payload-bytes", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--keep", action="store_true", help="Keep uploaded objects")
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Measure repeated POST and GET throughput and latency",
    )
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmup-rounds", type=int, default=1)
    parser.add_argument("--label", help="Backend name shown in benchmark results")
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    for name in ("count", "workers", "payload_bytes"):
        if getattr(args, name) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be at least 1")
    if args.timeout <= 0:
        raise ValueError("--timeout must be greater than 0")
    if args.rounds < 1:
        raise ValueError("--rounds must be at least 1")
    if args.warmup_rounds < 0:
        raise ValueError("--warmup-rounds must be at least 0")


def create_targets(
    storage: AbstractStorage, prefix: str, count: int
) -> list[UploadTarget]:
    targets = []
    for index in range(count):
        key = f"{prefix}/{index:06d}.bin"
        presigned = storage.get_upload_presigned_url_data(key)
        targets.append(
            UploadTarget(
                key=key,
                url=str(presigned["url"]),
                fields={
                    str(key): str(value) for key, value in presigned["fields"].items()
                },
            )
        )
    return targets


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def get_http_session() -> requests.Session:
    session = getattr(_thread_state, "session", None)
    if session is None:
        session = requests.Session()
        _thread_state.session = session
    return session


def timed_upload(
    target: UploadTarget, payload: bytes, timeout: float
) -> TransferResult:
    started_at = perf_counter()
    response = get_http_session().post(
        target.url,
        data=target.fields,
        files={"file": (target.key, payload, "application/octet-stream")},
        timeout=timeout,
    )
    elapsed = perf_counter() - started_at
    try:
        return TransferResult(target.key, response.status_code, elapsed)
    finally:
        response.close()


def timed_download(
    target: DownloadTarget, payload: bytes, timeout: float
) -> TransferResult:
    started_at = perf_counter()
    response = get_http_session().get(target.url, timeout=timeout)
    content = response.content
    elapsed = perf_counter() - started_at
    try:
        return TransferResult(
            target.key,
            response.status_code,
            elapsed,
            content_matches=content == payload,
        )
    finally:
        response.close()


def run_transfers(
    targets: list[TransferTarget],
    payload: bytes,
    workers: int,
    timeout: float,
    transfer: Callable[[TransferTarget, bytes, float], TransferResult],
) -> tuple[list[TransferResult], float]:
    started_at = perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(transfer, target, payload, timeout) for target in targets
        ]
        results = [future.result() for future in as_completed(futures)]
    return results, perf_counter() - started_at


def create_round_result(
    operation: str,
    round_number: int,
    warmup: bool,
    results: list[TransferResult],
    elapsed_seconds: float,
    payload_bytes: int,
) -> RoundResult:
    errors = sum(not succeeded(operation, result) for result in results)
    latencies_ms = [result.seconds * 1000 for result in results]
    transferred_mib = len(results) * payload_bytes / (1024 * 1024)
    return RoundResult(
        operation=operation,
        round_number=round_number,
        warmup=warmup,
        requests=len(results),
        errors=errors,
        elapsed_seconds=elapsed_seconds,
        operations_per_second=len(results) / elapsed_seconds,
        mebibytes_per_second=transferred_mib / elapsed_seconds,
        latency_p50_ms=percentile(latencies_ms, 0.50),
        latency_p95_ms=percentile(latencies_ms, 0.95),
        latency_p99_ms=percentile(latencies_ms, 0.99),
    )


def succeeded(operation: str, result: TransferResult) -> bool:
    return result.status in SUCCESSFUL_STATUSES[operation] and result.content_matches


def ensure_transfers_succeeded(operation: str, results: list[TransferResult]) -> None:
    failures = [result for result in results if not succeeded(operation, result)]
    if failures:
        details = [
            {
                "key": result.key,
                "status": result.status,
                "content_matches": result.content_matches,
            }
            for result in failures[:10]
        ]
        raise RuntimeError(f"{operation} failures ({len(failures)}): {details}")


def summarize_rounds(
    operation: str,
    rounds: list[RoundResult],
    samples: list[TransferResult],
    payload_bytes: int,
) -> dict[str, Any]:
    measured_rounds = [
        result
        for result in rounds
        if result.operation == operation and not result.warmup
    ]
    total_requests = sum(result.requests for result in measured_rounds)
    total_seconds = sum(result.elapsed_seconds for result in measured_rounds)
    latencies_ms = [sample.seconds * 1000 for sample in samples]
    return {
        "operation": operation,
        "rounds": len(measured_rounds),
        "requests": total_requests,
        "errors": sum(result.errors for result in measured_rounds),
        "operations_per_second": total_requests / total_seconds,
        "mebibytes_per_second": (
            total_requests * payload_bytes / (1024 * 1024) / total_seconds
        ),
        "latency_p50_ms": percentile(latencies_ms, 0.50),
        "latency_p95_ms": percentile(latencies_ms, 0.95),
        "latency_p99_ms": percentile(latencies_ms, 0.99),
    }


def cleanup(
    storage: AbstractStorage, targets: list[UploadTarget], workers: int
) -> None:
    # Best-effort: cleanup runs from a finally block, so raising here would
    # replace the failure the caller is actually reporting.
    def remove(key: str) -> str | None:
        try:
            if storage.does_exist(key):
                storage.delete(key)
        except Exception as error:
            return f"{key}: {error}"
        return None

    # Pooled because cleanup is two round trips per object: run serially, at
    # benchmark sizes (--count 5000 over several rounds) it dominated the run.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(remove, target.key) for target in targets]
        failures = [result for result in (f.result() for f in futures) if result]

    if failures:
        print(
            f"WARN cleanup left {len(failures)} object(s) behind: {failures[:5]}",
            file=sys.stderr,
        )


def run_check(args: argparse.Namespace, storage: AbstractStorage) -> None:
    prefix = f"e2e/presigned-post/{uuid4()}"
    payload = os.urandom(args.payload_bytes)
    targets = create_targets(storage, prefix, args.count)

    started_at = perf_counter()
    try:
        results, upload_elapsed = run_transfers(
            targets, payload, args.workers, args.timeout, timed_upload
        )
        ensure_transfers_succeeded("POST", results)

        missing_or_corrupt = [
            target.key for target in targets if storage.get(target.key) != payload
        ]
        if missing_or_corrupt:
            raise RuntimeError(
                f"missing or corrupt objects ({len(missing_or_corrupt)}): "
                f"{missing_or_corrupt[:10]}"
            )

        total_elapsed = perf_counter() - started_at
        print(
            "PASS "
            f"uploaded={len(results)}/{args.count} "
            f"verified={args.count}/{args.count} "
            f"workers={args.workers} payload_bytes={args.payload_bytes} "
            f"upload_seconds={upload_elapsed:.3f} "
            f"total_seconds={total_elapsed:.3f}"
        )
    finally:
        if not args.keep:
            cleanup(storage, targets, args.workers)


def run_benchmark(args: argparse.Namespace, storage: AbstractStorage) -> None:
    payload = os.urandom(args.payload_bytes)
    round_results: list[RoundResult] = []
    measured_samples: dict[str, list[TransferResult]] = {"POST": [], "GET": []}
    total_rounds = args.warmup_rounds + args.rounds

    for round_index in range(total_rounds):
        round_number = round_index + 1
        warmup = round_index < args.warmup_rounds
        prefix = f"benchmark/presigned/{uuid4()}"
        upload_targets = create_targets(storage, prefix, args.count)
        try:
            put_results, put_elapsed = run_transfers(
                upload_targets,
                payload,
                args.workers,
                args.timeout,
                timed_upload,
            )
            ensure_transfers_succeeded("POST", put_results)
            put_round = create_round_result(
                "POST",
                round_number,
                warmup,
                put_results,
                put_elapsed,
                args.payload_bytes,
            )
            round_results.append(put_round)

            download_targets = [
                DownloadTarget(
                    target.key, storage.get_download_presigned_url(target.key)
                )
                for target in upload_targets
            ]
            get_results, get_elapsed = run_transfers(
                download_targets,
                payload,
                args.workers,
                args.timeout,
                timed_download,
            )
            ensure_transfers_succeeded("GET", get_results)
            get_round = create_round_result(
                "GET",
                round_number,
                warmup,
                get_results,
                get_elapsed,
                args.payload_bytes,
            )
            round_results.append(get_round)

            if not warmup:
                measured_samples["POST"].extend(put_results)
                measured_samples["GET"].extend(get_results)

            phase = "warmup" if warmup else "measured"
            print(
                f"ROUND {round_number}/{total_rounds} {phase} "
                f"POST={put_round.operations_per_second:.2f}ops/s "
                f"GET={get_round.operations_per_second:.2f}ops/s "
                f"errors={put_round.errors + get_round.errors}"
            )
        finally:
            if not args.keep:
                cleanup(storage, upload_targets, args.workers)

    summaries = [
        summarize_rounds(
            operation,
            round_results,
            measured_samples[operation],
            args.payload_bytes,
        )
        for operation in ("POST", "GET")
    ]
    label = args.label or os.environ["STORAGE_SEAWEEDFS_ENDPOINT_URL"]
    print(
        "\nBackend | Operation | Size | Workers | Ops/s | MiB/s | p50 ms | "
        "p95 ms | p99 ms | Errors"
    )
    print("--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---:")
    for summary in summaries:
        print(
            f"{label} | {summary['operation']} | {args.payload_bytes} B | "
            f"{args.workers} | {summary['operations_per_second']:.2f} | "
            f"{summary['mebibytes_per_second']:.2f} | "
            f"{summary['latency_p50_ms']:.2f} | "
            f"{summary['latency_p95_ms']:.2f} | "
            f"{summary['latency_p99_ms']:.2f} | {summary['errors']}"
        )

    if args.output_json:
        report = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label": label,
            "endpoint": os.environ["STORAGE_SEAWEEDFS_ENDPOINT_URL"],
            "bucket": os.environ["STORAGE_SEAWEEDFS_BUCKET_NAME"],
            "parameters": {
                "count": args.count,
                "workers": args.workers,
                "payload_bytes": args.payload_bytes,
                "rounds": args.rounds,
                "warmup_rounds": args.warmup_rounds,
                "timeout": args.timeout,
            },
            "system": {
                "platform": platform.platform(),
                "python": sys.version,
            },
            "summaries": summaries,
            "rounds": [asdict(result) for result in round_results],
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        print(f"JSON {args.output_json}")


def run(args: argparse.Namespace) -> None:
    validate_args(args)
    if os.environ.get("STORAGE_DRIVER") != "seaweedfs":
        raise RuntimeError(
            "This check only runs with STORAGE_DRIVER=seaweedfs to avoid "
            "writing test objects to production S3."
        )

    storage = get_storage()
    if args.benchmark:
        run_benchmark(args, storage)
    else:
        run_check(args, storage)


def main() -> None:
    try:
        run(parse_args())
    except KeyError as error:
        # get_storage() reads the STORAGE_SEAWEEDFS_* settings with environ[].
        print(f"FAIL missing environment variable: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    except (ValueError, RuntimeError, requests.RequestException) as error:
        print(f"FAIL {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
