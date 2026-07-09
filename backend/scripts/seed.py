#!/usr/bin/env python3
"""Seed the local development database with the canonical test data.

The seed set used to live in `db/init/*.sql` (raw SQL executed by docker init).
After moving schema management to Alembic, this script became the single
source of truth for local seed data. It is **idempotent**: re-running it does
not duplicate rows.

Run via `make seed` (preferred) or directly:

    cd backend
    ENV=local DB_HOST=localhost DB_NAME=main DB_CONNECTOR=mysql+pymysql \
        uv run python scripts/seed.py
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from oqtopus_cloud.common.models import (
    Device,
    Job,
    User,
    WhitelistUser,
)
from oqtopus_cloud.common.session import get_db

_NOW = datetime.datetime.now(datetime.timezone.utc)
_EXPIRED_TOKEN = datetime.datetime(2021, 1, 1, 0, 0, 5, tzinfo=datetime.timezone.utc)

# Fixed, monotonically increasing lifecycle timestamps for the succeeded job so
# submitted -> ready -> running -> ended is internally consistent (and stable
# across re-seeds, unlike _NOW).
_SUBMITTED_AT = datetime.datetime(2024, 3, 4, 12, 0, 0, tzinfo=datetime.timezone.utc)
_READY_AT = datetime.datetime(2024, 3, 4, 12, 0, 30, tzinfo=datetime.timezone.utc)
_RUNNING_AT = datetime.datetime(2024, 3, 4, 12, 1, 0, tzinfo=datetime.timezone.utc)
_ENDED_AT = datetime.datetime(2024, 3, 4, 12, 1, 16, tzinfo=datetime.timezone.utc)


DEVICES: list[dict[str, Any]] = [
    {
        "id": "SC",
        "device_type": "QPU",
        "status": "available",
        "available_at": _NOW,
        "pending_jobs": 9,
        "n_qubits": 64,
        "basis_gates": json.dumps(["sx", "rz", "rzx90", "id"]),
        "instructions": json.dumps(["measure", "barrier"]),
        "device_info": "",
        "calibrated_at": _NOW,
        "description": "Superconducting quantum computer",
    },
    {
        "id": "SVSim",
        "device_type": "simulator",
        "status": "available",
        "available_at": _NOW,
        "pending_jobs": 0,
        "n_qubits": 39,
        "basis_gates": json.dumps(
            [
                "x", "y", "z", "h", "s", "sdg", "t", "tdg",
                "rx", "ry", "rz", "cx", "cz", "swap",
                "u1", "u2", "u3", "u", "p", "id", "sx", "sxdg",
            ]
        ),
        "instructions": json.dumps(["measure", "barrier", "reset"]),
        "device_info": "",
        "calibrated_at": _NOW,
        "description": "State vector-based quantum circuit simulator",
    },
    {
        "id": "Kawasaki",
        "device_type": "QPU",
        "status": "available",
        "available_at": _NOW,
        "pending_jobs": 2,
        "n_qubits": 64,
        "basis_gates": json.dumps(["sx", "rz", "rzx90", "id"]),
        "instructions": json.dumps(["measure", "barrier"]),
        "device_info": "",
        "calibrated_at": _NOW,
        "description": "Superconducting quantum computer",
    },
    {
        "id": "01927422-86d4-7597-b724-b08a5e7781fc",
        "device_type": "QPU",
        "status": "unavailable",
        "available_at": _NOW,
        "pending_jobs": 0,
        "n_qubits": 64,
        "basis_gates": json.dumps(["sx", "rz", "rzx90", "id"]),
        "instructions": json.dumps(["measure", "barrier"]),
        "device_info": "",
        "calibrated_at": _NOW,
        "description": "Superconducting quantum computer",
    },
    {
        "id": "qulacs",
        "device_type": "simulator",
        "status": "available",
        "available_at": _NOW,
        "pending_jobs": 0,
        "n_qubits": 16,
        "basis_gates": json.dumps(["sx", "x", "rz", "cx"]),
        "instructions": json.dumps(["measure", "barrier"]),
        "device_info": "",
        "calibrated_at": _NOW,
        "description": "Qulacs Simulator",
    },
]


_TRANSPILER_INFO = json.dumps(
    {
        "qubit_allocation": {"0": 12, "1": 16},
        "skip_transpilation": False,
        "seed_transpilation": 873,
    }
)
_SIMULATOR_INFO = json.dumps(
    {
        "n_qubits": 5,
        "n_nodes": 12,
        "n_per_node": 2,
        "seed_simulation": 39058567,
        "simulation_opt": {
            "optimization_method": "light",
            "optimization_block_size": 1,
            "optimization_swap_level": 1,
        },
    }
)
_MITIGATION_INFO = json.dumps({"ro_error_mitigation": "pseudo_inverse"})


# NOTE: keep in sync with storage/init_storage.py — it uploads the storage
# objects (input.zip, plus one <name>.zip per entry in output_files) that the
# API's get_job_info() dereferences for each of these jobs. A job's DB row and
# its MinIO objects must agree, or download URLs 404.
JOBS: list[dict[str, Any]] = [
    # Job 1: a completed run. execution_time / ended_at are set, and
    # output_files + message reflect the result artifacts the provider uploaded.
    {
        "id": "21927422-86d4-73d6-abb4-f2de6a4f5910",
        "owner": "admin",
        "name": "Test job 1",
        "description": "Test job 1 description",
        "device_id": "qulacs",
        "transpiler_info": _TRANSPILER_INFO,
        "simulator_info": _SIMULATOR_INFO,
        "mitigation_info": _MITIGATION_INFO,
        "job_type": "sampling",
        "shots": 1000,
        "status": "succeeded",
        "execution_time": Decimal("15.8"),
        "output_files": json.dumps(["result", "transpile_result"]),
        "message": "Job completed successfully",
        "submitted_at": _SUBMITTED_AT,
        "ready_at": _READY_AT,
        "running_at": _RUNNING_AT,
        "ended_at": _ENDED_AT,
    },
    # Job 2: freshly submitted. It has not run yet, so execution_time and the
    # ready/running/ended timestamps are NULL and there are no output_files.
    {
        "id": "21927422-86d4-7cbf-98d3-32f5f1263cd9",
        "owner": "admin",
        "name": "Test job 2",
        "description": "Test job 2 description",
        "device_id": "qulacs",
        "transpiler_info": _TRANSPILER_INFO,
        "simulator_info": _SIMULATOR_INFO,
        "mitigation_info": _MITIGATION_INFO,
        "job_type": "sampling",
        "shots": 1000,
        "status": "submitted",
        "execution_time": None,
        "output_files": None,
        "message": None,
        "submitted_at": _SUBMITTED_AT,
        "ready_at": None,
        "running_at": None,
        "ended_at": None,
    },
]


USERS: list[dict[str, Any]] = [
    {
        "id": "admin-email",
        "cognito_id": "3704aaf8-a0e1-70c5-b5eb-e3879fd201dd",
        "email": "admin-email",
        "display_name": "admin",
        "userstatus": "approved",
        "organization": "admin-organization",
        "group_id": "admin-group_id",
        "available_devices": "*",
        "mfa_status": "disabled",
        "api_token_id": "admin-api_token_id",
        "api_token_hash": "$2a$12$lY9LC0MxhEpkM43h1xZCCu3DjxwQ6za0aOr2vNIOe5OlFiN9UjHTm",
        "api_token_expiration": _EXPIRED_TOKEN,
    },
    {
        "id": "admin-email@admin-email",
        "cognito_id": "c7740a88-4011-70b9-f031-4656382f880e",
        "email": "admin-email@admin-email",
        "display_name": "admin2",
        "userstatus": "approved",
        "organization": "admin-organization2",
        "group_id": "admin-group_id2",
        "available_devices": "*",
        "mfa_status": "disabled",
        "api_token_id": "admin-api_token_id2",
        "api_token_hash": "$2a$12$RvzbOOHLt18aDrfoTfuuZ.G.K4P.gOh38R.Dij1u8Vu.Kph6dFR/O",
        "api_token_expiration": _EXPIRED_TOKEN,
    },
    {
        "id": "email-admin",
        "cognito_id": "d7740a88-4011-70b9-f031-4656382f880e",
        "email": "email-admin",
        "display_name": "admin3",
        "userstatus": "approved",
        "organization": "admin-organization3",
        "group_id": "admin-group_id3",
        "available_devices": "*",
        "mfa_status": "disabled",
        "api_token_id": "admin-api_token_id3",
        "api_token_hash": "$2a$12$srgz4gTm0kBLmDJvkX.XRexiz3VFn5vVtmquYoDLVnNjjDk6LtbPa",
        "api_token_expiration": _EXPIRED_TOKEN,
    },
    # Demo user for the flexible-auth (AUTH_MODE=oidc) local demonstration.
    # `id` == the email Keycloak issues for the LDAP-federated user, since the
    # OIDC middleware resolves user_id from the `email` claim. Provisioned as
    # `approved` so the in-app authorization check passes. No API token: this
    # user authenticates interactively via oauth2-proxy + Keycloak, not q-api-token.
    {
        "id": "demo@oqtopus.local",
        "cognito_id": "ldap-demo-0001",
        "email": "demo@oqtopus.local",
        "display_name": "OQTOPUS Demo User",
        "userstatus": "approved",
        "organization": "OQTOPUS Demo Org",
        "group_id": "demo-group",
        "available_devices": "*",
        "mfa_status": "disabled",
        "api_token_id": None,
        "api_token_hash": None,
        "api_token_expiration": None,
    },
]


WHITELIST_USERS: list[dict[str, Any]] = [
    {
        "group_id": "group1",
        "email": "example1@example.com",
        "display_name": "exampleuser1",
        "organization": "Example Organization1",
        "is_signup_completed": True,
        "available_devices": "*",
    },
    {
        "group_id": "group2",
        "email": "example2@example.com",
        "display_name": "exampleuser2",
        "organization": "Example Organization2",
        "is_signup_completed": False,
        "available_devices": "*",
    },
    {
        "group_id": "group3",
        "email": "example3@example.com",
        "display_name": "exampleuser3",
        "organization": "Example Organization3",
        "is_signup_completed": True,
        "available_devices": "*",
    },
    {
        "group_id": "group4",
        "email": "example4@example.com",
        "display_name": "userexample4",
        "organization": "Example Organization2",
        "is_signup_completed": False,
        "available_devices": "*",
    },
]


def _upsert_by_pk(db: Session, model: type, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    for row in rows:
        if db.get(model, row["id"]) is None:
            db.add(model(**row))
            inserted += 1
    return inserted


def _upsert_whitelist_users(db: Session, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    for row in rows:
        existing = db.scalar(
            select(WhitelistUser).where(WhitelistUser.email == row["email"])
        )
        if existing is None:
            db.add(WhitelistUser(**row))
            inserted += 1
    return inserted


def main() -> None:
    db = next(get_db())
    try:
        n_devices = _upsert_by_pk(db, Device, DEVICES)
        n_jobs = _upsert_by_pk(db, Job, JOBS)
        n_users = _upsert_by_pk(db, User, USERS)
        n_whitelist = _upsert_whitelist_users(db, WHITELIST_USERS)
        db.commit()
        print(
            f"✅ Seeded: devices={n_devices}/{len(DEVICES)}, "
            f"jobs={n_jobs}/{len(JOBS)}, "
            f"users={n_users}/{len(USERS)}, "
            f"whitelist_users={n_whitelist}/{len(WHITELIST_USERS)} "
            f"(new/total — existing rows are skipped)"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
