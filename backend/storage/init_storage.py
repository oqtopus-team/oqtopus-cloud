#!/usr/bin/env python3
"""Seed the local object storage (SeaweedFS) to match the seeded job rows.

After the S3-offload change, a job's payload no longer lives in the DB: the API
(`get_job_info`) builds presigned URLs for ``{job_id}/input.zip`` and, for every
entry in the job's ``output_files`` column, ``{job_id}/{name}.zip``. Seeding
only the DB (scripts/seed.py) therefore leaves those URLs pointing at objects
that do not exist. This script uploads the matching objects so the DB rows and
storage stay consistent.

It is driven by the same ``JOBS`` list as scripts/seed.py, so the two cannot
drift, and it is **idempotent**: objects that already exist are left untouched.

Run via `make up` (which invokes it after `make seed`) or directly:

    cd backend
    STORAGE_DRIVER=seaweedfs STORAGE_SEAWEEDFS_BUCKET_NAME=... \
        STORAGE_SEAWEEDFS_USERNAME=... STORAGE_SEAWEEDFS_PASSWORD=... \
        STORAGE_SEAWEEDFS_ENDPOINT_URL=http://localhost:8333 \
        uv run python storage/init_storage.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile

# scripts/ is not an installed package; add the backend root to sys.path so the
# canonical seed data can be imported and shared (single source of truth).
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from oqtopus_cloud.common.storages import AbstractStorage, get_storage  # noqa: E402
from oqtopus_cloud.common.storages.storage_utils import (  # noqa: E402
    JOB_INFO_INPUT_PARAM,
)
from scripts.seed import JOBS  # noqa: E402


def _zip_bytes(entries: dict[str, str]) -> bytes:
    """Build an in-memory zip from {filename: text} so seeded objects are real,
    openable archives rather than opaque placeholder bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, text in entries.items():
            zf.writestr(filename, text)
    return buf.getvalue()


# Payload bodies for each logical output-file name referenced by output_files.
_OUTPUT_PAYLOADS: dict[str, dict[str, str]] = {
    "result": {
        "result.json": json.dumps(
            {"counts": {"00": 84, "11": 387, "10": 454, "01": 75}}
        )
    },
    "transpile_result": {
        "transpile_result.json": json.dumps(
            {"virtual_physical_mapping": {"0": 0, "1": 1}}
        )
    },
}

_INPUT_PAYLOAD = {
    "program.qasm": (
        'OPENQASM 3; include "stdgates.inc"; qubit[2] q; bit[2] c; '
        "h q[0]; cnot q[0], q[1]; c = measure q;"
    )
}


def _object_manifest() -> dict[str, bytes]:
    """Map every required storage key to its payload, derived from JOBS."""
    manifest: dict[str, bytes] = {}
    for job in JOBS:
        job_id = job["id"]
        # Every submitted (non-registered) job has an uploaded input.
        manifest[f"{job_id}/{JOB_INFO_INPUT_PARAM}.zip"] = _zip_bytes(_INPUT_PAYLOAD)
        output_files = job.get("output_files")
        if not output_files:
            continue
        for name in json.loads(output_files):
            manifest[f"{job_id}/{name}.zip"] = _zip_bytes(
                _OUTPUT_PAYLOADS.get(name, {f"{name}.txt": name})
            )
    return manifest


def _seed_storage(storage: AbstractStorage) -> tuple[int, int]:
    manifest = _object_manifest()
    uploaded = 0
    for key, data in manifest.items():
        if storage.does_exist(key):
            continue
        storage.put(key, data)
        uploaded += 1
    return uploaded, len(manifest)


def main() -> None:
    driver = os.environ.get("STORAGE_DRIVER", "s3")
    if driver not in ("local", "seaweedfs"):
        # Guard against accidentally writing seed objects to a real S3 bucket.
        print(
            f"⏭️  Skipping storage seed: STORAGE_DRIVER={driver!r} is not a "
            "self-hosted driver (expected 'local' or 'seaweedfs')."
        )
        return

    storage = get_storage()
    uploaded, total = _seed_storage(storage)
    print(
        f"✅ Storage seeded: objects={uploaded}/{total} "
        f"(new/total — existing objects are skipped)"
    )


if __name__ == "__main__":
    main()
