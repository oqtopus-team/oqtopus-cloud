from __future__ import annotations

import argparse
import ast
import base64
import boto3
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from oqtopus_cloud.common.models.job import Job  # noqa: E402
from oqtopus_cloud.common.session import get_db  # noqa: E402
from oqtopus_cloud.common.storages import get_storage  # noqa: E402
from oqtopus_cloud.common.storages.abstract_storage import (  # noqa: E402
    AbstractStorage,
)
from oqtopus_cloud.common.storages.storage_utils import (  # noqa: E402
    JOB_INFO_COMBINED_PROGRAM_PARAM,
    JOB_INFO_INPUT_PARAM,
    JOB_INFO_RESULT_PARAM,
    JOB_INFO_SSE_LOG_PARAM,
    JOB_INFO_TRANSPILE_RESULT_PARAM,
)


INPUT_PAYLOAD_KEYS = {"program", "operator", "sse_program"}
OUTPUT_ARTIFACT_NAMES = (
    JOB_INFO_COMBINED_PROGRAM_PARAM,
    JOB_INFO_TRANSPILE_RESULT_PARAM,
    JOB_INFO_RESULT_PARAM,
    JOB_INFO_SSE_LOG_PARAM,
)
ARTIFACT_ALIASES = {
    JOB_INFO_INPUT_PARAM: (
        "input",
        "job_input",
        "submit_job_info",
        "s3_submit_job_info",
    ),
    JOB_INFO_COMBINED_PROGRAM_PARAM: ("combined_program", "combinedProgram"),
    JOB_INFO_TRANSPILE_RESULT_PARAM: (
        "transpile_result",
        "transpiled_result",
        "transpileResult",
        "transpiledResult",
    ),
    JOB_INFO_RESULT_PARAM: ("result", "job_result", "jobResult"),
    JOB_INFO_SSE_LOG_PARAM: ("sse_log", "sseLog", "log", "logs"),
}
SUCCESS_STATUSES = {"succeeded"}
SOURCE_COMMANDS = {"dry-run", "migrate", "verify"}
TARGET_DB_COMMANDS = {
    "prepare-schema",
    "schema-status",
    "migrate",
    "verify",
    "cleanup-schema",
    "cutover",
}
JOBS_TABLE_NAME = "jobs"


class MigrationError(Exception):
    pass


@dataclass
class LegacyJobRecord:
    row: dict[str, Any]
    external_payloads: dict[str, Any] = field(default_factory=dict)

    @property
    def job_id(self) -> str:
        return str(self.row["id"])

    @property
    def status(self) -> str:
        return str(self.row.get("status") or "submitted")


@dataclass
class MigrationPlan:
    input_payload: Any
    output_payloads: dict[str, Any]
    output_files: list[str]
    message: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy jobs rows into storage-backed jobs records.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("prepare-schema", "schema-status", "cleanup-schema"):
        subparser = subparsers.add_parser(command)
        _add_schema_arguments(subparser)

    for command in ("dry-run", "migrate", "verify"):
        subparser = subparsers.add_parser(command)
        _add_source_arguments(subparser)
        _add_common_arguments(subparser)
        _add_schema_arguments(subparser)

    cutover_parser = subparsers.add_parser("cutover")
    _add_source_arguments(cutover_parser)
    _add_common_arguments(cutover_parser)
    _add_schema_arguments(cutover_parser)
    cutover_parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Keep the legacy job_info column after a successful verify",
    )

    return parser.parse_args()


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-current-db",
        action="store_true",
        help="Read legacy rows from the current target DB before cleanup",
    )
    parser.add_argument("--source-dsn", help="SQLAlchemy DSN for the legacy jobs DB")
    parser.add_argument(
        "--source-table",
        default="jobs",
        help="Legacy source table name when --source-dsn is used",
    )
    parser.add_argument(
        "--source-query",
        help="Custom SQL query when --source-dsn is used; must include legacy job_info",
    )
    parser.add_argument(
        "--source-json",
        help="Path to a JSON file containing a list of legacy rows",
    )
    parser.add_argument(
        "--source-jsonl",
        help="Path to a JSONL file containing one legacy row per line",
    )
    parser.add_argument(
        "--legacy-sse-log-prefix",
        help="Optional object storage key prefix above the legacy SSE log key pattern",
    )
    parser.add_argument(
        "--legacy-sse-log-pattern",
        default="{job_id}/ssecontainer.log",
        help="Object storage key pattern for legacy SSE logs; old SSE jobs stored logs under job_id/ssecontainer.log",
    )


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--job-id", action="append", help="Restrict migration to job id")
    parser.add_argument("--limit", type=int, help="Maximum number of jobs to process")
    parser.add_argument(
        "--allow-missing-result",
        action="store_true",
        help="Do not fail succeeded jobs when no result payload is found",
    )


def _add_schema_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target-dsn",
        help="SQLAlchemy DSN for the target jobs DB; defaults to the environment-backed current DB",
    )
    parser.add_argument(
        "--target-table",
        default=JOBS_TABLE_NAME,
        help="Target jobs table name for schema operations",
    )


def main() -> int:
    args = parse_args()
    apply_default_source(args)
    target_db: Session | None = None
    db_generator = None
    target_engine = None
    storage: AbstractStorage | None = None

    try:
        if should_open_target_db(args):
            if args.target_dsn:
                target_engine, target_db = open_db_session_from_dsn(args.target_dsn)
            else:
                apply_current_db_env_aliases()
                db_generator = get_db()
                target_db = next(db_generator)

        if should_open_storage(args):
            storage = get_storage()

        if args.command in SOURCE_COMMANDS or args.command == "cutover":
            validate_source_args(args)
            jobs = list(iter_source_rows(args, target_db, storage))
            if args.command == "dry-run":
                return run_dry_run(jobs, args)

        if args.command == "prepare-schema":
            return run_prepare_schema(require_target_db(target_db), args)
        if args.command == "schema-status":
            return run_schema_status(require_target_db(target_db), args)
        if args.command == "migrate":
            return run_migrate(jobs, require_target_db(target_db), storage, args)
        if args.command == "verify":
            return run_verify(jobs, require_target_db(target_db), storage, args)
        if args.command == "cutover":
            return run_cutover(jobs, require_target_db(target_db), storage, args)
        return run_cleanup_schema(require_target_db(target_db), args)
    finally:
        if target_db is not None:
            target_db.close()
        if target_engine is not None:
            target_engine.dispose()
        if db_generator is not None:
            db_generator.close()


def apply_current_db_env_aliases() -> None:
    env_aliases = (
        ("SECRET_ID", "SECRET_NAME"),
        ("PROFILE", "AWS_PROFILE"),
        ("MYSQL_PORT", "DB_PORT"),
    )
    for source_name, target_name in env_aliases:
        if os.environ.get(target_name) in (None, ""):
            source_value = os.environ.get(source_name)
            if source_value is not None and source_value != "":
                os.environ[target_name] = source_value

    if os.environ.get("DB_HOST") in (None, ""):
        os.environ["DB_HOST"] = "localhost"

    if os.environ.get("AWS_REGION") in (None, ""):
        default_region = os.environ.get("AWS_DEFAULT_REGION")
        if default_region is not None and default_region != "":
            os.environ["AWS_REGION"] = default_region
        else:
            profile = os.environ.get("AWS_PROFILE")
            session = boto3.session.Session(profile_name=profile)
            if session.region_name not in (None, ""):
                os.environ["AWS_REGION"] = session.region_name


def should_open_target_db(args: argparse.Namespace) -> bool:
    return args.command in TARGET_DB_COMMANDS or getattr(args, "source_current_db", False)


def should_open_storage(args: argparse.Namespace) -> bool:
    return args.command in {"migrate", "verify", "cutover"} or bool(
        getattr(args, "legacy_sse_log_prefix", None)
    )


def apply_default_source(args: argparse.Namespace) -> None:
    if args.command != "cutover":
        return

    explicit_source_count = sum(
        bool(value)
        for value in (
            getattr(args, "source_current_db", False),
            getattr(args, "source_dsn", None),
            getattr(args, "source_json", None),
            getattr(args, "source_jsonl", None),
        )
    )
    if explicit_source_count == 0:
        args.source_current_db = True


def require_target_db(target_db: Session | None) -> Session:
    if target_db is None:
        raise MigrationError("target DB session is required for this command")
    return target_db


def open_db_session_from_dsn(dsn: str) -> tuple[Any, Session]:
    engine = create_engine(
        dsn,
        connect_args={
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'"
        },
    )
    return engine, Session(bind=engine)


def validate_source_args(args: argparse.Namespace) -> None:
    source_count = sum(
        bool(value)
        for value in (
            getattr(args, "source_current_db", False),
            args.source_dsn,
            args.source_json,
            args.source_jsonl,
        )
    )
    if source_count != 1:
        raise SystemExit(
            "Specify exactly one source: --source-current-db, --source-dsn, --source-json or --source-jsonl"
        )


def iter_source_rows(
    args: argparse.Namespace,
    target_db: Session | None = None,
    storage: AbstractStorage | None = None,
) -> Iterator[LegacyJobRecord]:
    if args.source_current_db:
        rows = list(iter_source_rows_from_target_db(args, require_target_db(target_db)))
    elif args.source_json:
        data = json.loads(Path(args.source_json).read_text())
        if not isinstance(data, list):
            raise MigrationError("source json must contain a list of rows")
        rows = data
    elif args.source_jsonl:
        rows = [json.loads(line) for line in Path(args.source_jsonl).read_text().splitlines() if line.strip()]
    else:
        rows = list(iter_source_rows_from_db(args))

    seen = 0
    selected_job_ids = set(args.job_id or [])
    for row in rows:
        if not isinstance(row, dict):
            raise MigrationError("legacy row must be a JSON object")
        record = LegacyJobRecord(
            row=row,
            external_payloads=load_external_payloads(args, row, storage),
        )
        if selected_job_ids and record.job_id not in selected_job_ids:
            continue
        yield record
        seen += 1
        if args.limit is not None and seen >= args.limit:
            return


def iter_source_rows_from_db(args: argparse.Namespace) -> Iterator[dict[str, Any]]:
    query = args.source_query or f"SELECT * FROM {args.source_table}"
    engine = create_engine(args.source_dsn)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(query))
            for row in result.mappings():
                yield dict(row)
    finally:
        engine.dispose()


def iter_source_rows_from_target_db(
    args: argparse.Namespace,
    target_db: Session,
) -> Iterator[dict[str, Any]]:
    query = args.source_query or f"SELECT * FROM {args.target_table}"
    result = target_db.execute(text(query))
    for row in result.mappings():
        yield dict(row)


def run_prepare_schema(target_db: Session, args: argparse.Namespace) -> int:
    existing_columns = get_table_columns(target_db, args.target_table)
    statements: list[str] = []

    if "output_files" not in existing_columns:
        statements.append(
            f"ALTER TABLE {args.target_table} ADD COLUMN output_files TEXT AFTER mitigation_info"
        )
    if "message" not in existing_columns:
        statements.append(
            f"ALTER TABLE {args.target_table} ADD COLUMN message TEXT AFTER output_files"
        )

    if not statements:
        print("schema already prepared")
        return 0

    for statement in statements:
        target_db.execute(text(statement))
    target_db.commit()
    print("schema prepared")
    return 0


def run_schema_status(target_db: Session, args: argparse.Namespace) -> int:
    existing_columns = get_table_columns(target_db, args.target_table)
    print(
        "\t".join(
            [
                args.target_table,
                f"job_info={'present' if 'job_info' in existing_columns else 'missing'}",
                f"output_files={'present' if 'output_files' in existing_columns else 'missing'}",
                f"message={'present' if 'message' in existing_columns else 'missing'}",
            ]
        )
    )
    return 0


def run_cleanup_schema(target_db: Session, args: argparse.Namespace) -> int:
    existing_columns = get_table_columns(target_db, args.target_table)
    if "job_info" not in existing_columns:
        print("legacy column already removed")
        return 0

    target_db.execute(text(f"ALTER TABLE {args.target_table} DROP COLUMN job_info"))
    target_db.commit()
    print("legacy column removed")
    return 0


def run_cutover(
    jobs: Sequence[LegacyJobRecord],
    target_db: Session,
    storage: Any,
    args: argparse.Namespace,
) -> int:
    prepare_status = run_prepare_schema(target_db, args)
    if prepare_status != 0:
        return prepare_status

    migrate_status = run_migrate(jobs, target_db, storage, args)
    if migrate_status != 0:
        return migrate_status

    verify_status = run_verify(jobs, target_db, storage, args)
    if verify_status != 0:
        return verify_status

    if args.skip_cleanup:
        print("cleanup skipped")
        return 0

    return run_cleanup_schema(target_db, args)


def get_table_columns(target_db: Session, table_name: str) -> set[str]:
    result = target_db.execute(text(f"SHOW COLUMNS FROM {table_name}"))
    return {str(row[0]) for row in result.fetchall()}


def run_dry_run(
    jobs: Sequence[LegacyJobRecord],
    args: argparse.Namespace,
) -> int:
    failures = 0
    for record in jobs:
        try:
            plan = build_plan(record, args.allow_missing_result)
            artifact_names = [JOB_INFO_INPUT_PARAM, *plan.output_files]
            print(f"{record.job_id}\tplan\tartifacts={','.join(artifact_names)}")
        except Exception as exc:
            failures += 1
            print(f"{record.job_id}\terror\t{exc}")
    return 1 if failures else 0


def run_migrate(
    jobs: Sequence[LegacyJobRecord],
    target_db: Session,
    storage: Any,
    args: argparse.Namespace,
) -> int:
    ensure_target_schema_ready(target_db, args)
    failures = 0
    for record in jobs:
        try:
            plan = build_plan(record, args.allow_missing_result)
            migrate_job(record, plan, target_db, storage)
            print(f"{record.job_id}\tmigrated")
        except Exception as exc:
            target_db.rollback()
            failures += 1
            print(f"{record.job_id}\terror\t{exc}")
    return 1 if failures else 0


def run_verify(
    jobs: Sequence[LegacyJobRecord],
    target_db: Session,
    storage: Any,
    args: argparse.Namespace,
) -> int:
    ensure_target_schema_ready(target_db, args)
    failures = 0
    for record in jobs:
        try:
            plan = build_plan(record, args.allow_missing_result)
            verify_job(record, plan, target_db, storage)
            print(f"{record.job_id}\tverified")
        except Exception as exc:
            failures += 1
            print(f"{record.job_id}\terror\t{exc}")
    return 1 if failures else 0


def build_plan(record: LegacyJobRecord, allow_missing_result: bool) -> MigrationPlan:
    legacy_job_info = parse_payload(record.row.get("job_info"))
    input_payload = extract_input_payload(record.row, legacy_job_info)
    output_payloads = extract_output_payloads(
        record.row,
        legacy_job_info,
        record.external_payloads,
    )
    output_payloads = normalize_output_payloads(output_payloads)
    if record.status in SUCCESS_STATUSES:
        if JOB_INFO_RESULT_PARAM not in output_payloads and not allow_missing_result:
            raise MigrationError("succeeded job is missing result payload")
    output_files = [name for name in OUTPUT_ARTIFACT_NAMES if name in output_payloads]
    message = coerce_optional_string(record.row.get("message"))
    if message is None and isinstance(legacy_job_info, dict):
        message = coerce_optional_string(legacy_job_info.get("message"))
    if message is None and isinstance(legacy_job_info, dict):
        message = coerce_optional_string(legacy_job_info.get("reason"))
    return MigrationPlan(
        input_payload=input_payload,
        output_payloads=output_payloads,
        output_files=output_files,
        message=message,
    )


def ensure_target_schema_ready(target_db: Session, args: argparse.Namespace) -> None:
    existing_columns = get_table_columns(target_db, args.target_table)
    if "output_files" in existing_columns and "message" in existing_columns:
        return
    run_prepare_schema(target_db, args)


def migrate_job(
    record: LegacyJobRecord,
    plan: MigrationPlan,
    target_db: Session,
    storage: Any,
) -> None:
    put_zip(storage, artifact_key(record.job_id, JOB_INFO_INPUT_PARAM), plan.input_payload)
    for artifact_name, payload in plan.output_payloads.items():
        put_zip(storage, artifact_key(record.job_id, artifact_name), payload)

    job = target_db.get(Job, record.job_id)
    if job is None:
        job = Job(id=record.job_id, owner=str(record.row["owner"]), device_id=str(record.row["device_id"]))
        target_db.add(job)

    apply_row_to_job(job, record.row, plan)
    target_db.commit()


def verify_job(
    record: LegacyJobRecord,
    plan: MigrationPlan,
    target_db: Session,
    storage: Any,
) -> None:
    job = target_db.get(Job, record.job_id)
    if job is None:
        raise MigrationError("target job row not found")
    required_keys = [artifact_key(record.job_id, JOB_INFO_INPUT_PARAM)]
    required_keys.extend(artifact_key(record.job_id, name) for name in plan.output_files)
    missing = [key for key in required_keys if not storage.does_exist(key=key)]
    if missing:
        raise MigrationError(f"missing storage objects: {missing}")

    expected_output_files = plan.output_files
    actual_output_files = parse_output_files(job.output_files)
    if actual_output_files != expected_output_files:
        raise MigrationError(
            f"output_files mismatch: expected={expected_output_files}, actual={actual_output_files}"
        )


def apply_row_to_job(job: Job, row: dict[str, Any], plan: MigrationPlan) -> None:
    job.owner = str(row["owner"])
    job.name = coerce_optional_string(row.get("name"))
    job.description = coerce_optional_string(row.get("description"))
    job.device_id = str(row["device_id"])
    job.transpiler_info = coerce_json_text(row.get("transpiler_info"))
    job.simulator_info = coerce_json_text(row.get("simulator_info"))
    job.mitigation_info = coerce_json_text(row.get("mitigation_info"))
    job.job_type = normalize_job_type(str(row.get("job_type") or "sampling"))
    job.shots = coerce_optional_int(row.get("shots"))
    job.status = str(row.get("status") or "submitted")
    job.execution_time = coerce_optional_float(row.get("execution_time"))
    job.output_files = json.dumps(plan.output_files) if plan.output_files else None
    job.message = plan.message
    job.submitted_at = parse_datetime_value(row.get("submitted_at"))
    job.ready_at = parse_datetime_value(row.get("ready_at"))
    job.running_at = parse_datetime_value(row.get("running_at"))
    job.ended_at = parse_datetime_value(row.get("ended_at"))


def extract_input_payload(row: dict[str, Any], legacy_job_info: Any) -> Any:
    job_type = normalize_job_type(str(row.get("job_type") or "sampling"))

    for alias in ARTIFACT_ALIASES[JOB_INFO_INPUT_PARAM]:
        if alias in row and row[alias] not in (None, ""):
            return normalize_input_payload(parse_payload(row[alias]), job_type)

    if isinstance(legacy_job_info, dict):
        legacy_root_payload = extract_legacy_root_input_payload(legacy_job_info)
        if legacy_root_payload is not None:
            return normalize_input_payload(legacy_root_payload, job_type)

        legacy_desc_payload = extract_legacy_desc_input_payload(legacy_job_info)
        if legacy_desc_payload is not None:
            return normalize_input_payload(legacy_desc_payload, job_type)

        for alias in ARTIFACT_ALIASES[JOB_INFO_INPUT_PARAM]:
            if alias in legacy_job_info and legacy_job_info[alias] not in (None, ""):
                return normalize_input_payload(
                    parse_payload(legacy_job_info[alias]), job_type
                )
        if INPUT_PAYLOAD_KEYS.intersection(legacy_job_info.keys()):
            return normalize_input_payload(
                {
                    key: legacy_job_info[key]
                    for key in INPUT_PAYLOAD_KEYS
                    if legacy_job_info.get(key) is not None
                },
                job_type,
            )

        filtered_payload = {
            key: value
            for key, value in legacy_job_info.items()
            if key not in collect_non_input_keys()
        }
        if filtered_payload:
            return normalize_input_payload(filtered_payload, job_type)

    if legacy_job_info is None:
        raise MigrationError("legacy row is missing job_info payload")
    return normalize_input_payload(legacy_job_info, job_type)


def normalize_input_payload(payload: Any, job_type: str) -> Any:
    if job_type != "sse" or not isinstance(payload, dict):
        return payload

    if payload.get("sse_program") not in (None, ""):
        return payload

    program_value = payload.get("program")
    if isinstance(program_value, list):
        if len(program_value) != 1:
            raise MigrationError("legacy SSE input payload must contain exactly one program")
        program_value = program_value[0]

    if program_value in (None, ""):
        return payload
    if not isinstance(program_value, str):
        raise MigrationError("legacy SSE input payload program must be a string")

    decoded_program = decode_legacy_sse_program(program_value)
    normalized_payload = dict(payload)
    normalized_payload["sse_program"] = decoded_program
    normalized_payload.pop("program", None)
    return normalized_payload


def decode_legacy_sse_program(program_value: str) -> str:
    try:
        decoded_bytes = base64.b64decode(program_value, validate=True)
    except Exception:
        return program_value

    try:
        return decoded_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MigrationError("legacy SSE program is not valid UTF-8 after base64 decode") from exc


def extract_legacy_root_input_payload(legacy_job_info: dict[str, Any]) -> dict[str, Any] | None:
    input_payload: dict[str, Any] = {}

    if legacy_job_info.get("job_type") not in (None, ""):
        input_payload["job_type"] = legacy_job_info["job_type"]
    if legacy_job_info.get("operator") not in (None, ""):
        input_payload["operator"] = parse_payload(legacy_job_info["operator"])
    if legacy_job_info.get("sse_program") not in (None, ""):
        input_payload["sse_program"] = parse_payload(legacy_job_info["sse_program"])

    if legacy_job_info.get("program") not in (None, ""):
        input_payload["program"] = parse_payload(legacy_job_info["program"])
    elif legacy_job_info.get("code") not in (None, ""):
        code_payload = parse_payload(legacy_job_info["code"])
        input_payload["program"] = code_payload if isinstance(code_payload, list) else [code_payload]

    return input_payload or None


def extract_legacy_desc_input_payload(legacy_job_info: dict[str, Any]) -> dict[str, Any] | None:
    desc_payload = parse_payload(legacy_job_info.get("desc"))
    if not isinstance(desc_payload, dict):
        return None

    input_payload: dict[str, Any] = {}
    if desc_payload.get("job_type") not in (None, ""):
        input_payload["job_type"] = desc_payload["job_type"]
    if desc_payload.get("operator") not in (None, ""):
        input_payload["operator"] = parse_payload(desc_payload["operator"])
    if desc_payload.get("sse_program") not in (None, ""):
        input_payload["sse_program"] = parse_payload(desc_payload["sse_program"])

    if desc_payload.get("program") not in (None, ""):
        input_payload["program"] = parse_payload(desc_payload["program"])
    elif desc_payload.get("code") not in (None, ""):
        code_payload = parse_payload(desc_payload["code"])
        input_payload["program"] = code_payload if isinstance(code_payload, list) else [code_payload]

    return input_payload or None


def extract_output_payloads(
    row: dict[str, Any],
    legacy_job_info: Any,
    external_payloads: dict[str, Any],
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for artifact_name in OUTPUT_ARTIFACT_NAMES:
        payload = external_payloads.get(artifact_name)
        if payload is None:
            payload = extract_named_payload(row, legacy_job_info, artifact_name)
        if payload is not None:
            payloads[artifact_name] = payload
    return payloads


def normalize_output_payloads(payloads: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payloads)
    if JOB_INFO_SSE_LOG_PARAM in normalized:
        normalized[JOB_INFO_SSE_LOG_PARAM] = normalize_sse_log_payload(
            normalized[JOB_INFO_SSE_LOG_PARAM]
        )
    return normalized


def normalize_sse_log_payload(payload: Any) -> str:
    parsed_payload = parse_payload(payload)
    if isinstance(parsed_payload, bytes):
        return parsed_payload.decode("utf-8")
    if isinstance(parsed_payload, str):
        return parsed_payload
    return json.dumps(parsed_payload)


def extract_named_payload(
    row: dict[str, Any], legacy_job_info: Any, artifact_name: str
) -> Any | None:
    for alias in ARTIFACT_ALIASES[artifact_name]:
        if alias in row and row[alias] not in (None, ""):
            return parse_payload(row[alias])
    if isinstance(legacy_job_info, dict):
        if artifact_name == JOB_INFO_SSE_LOG_PARAM:
            return None
        for alias in ARTIFACT_ALIASES[artifact_name]:
            if alias in legacy_job_info and legacy_job_info[alias] not in (None, ""):
                return parse_payload(legacy_job_info[alias])
        legacy_alias_payload = extract_legacy_named_payload(legacy_job_info, artifact_name)
        if legacy_alias_payload is not None:
            return legacy_alias_payload
    return None


def extract_legacy_named_payload(legacy_job_info: dict[str, Any], artifact_name: str) -> Any | None:
    if artifact_name == JOB_INFO_RESULT_PARAM and legacy_job_info.get("result") not in (None, ""):
        return parse_payload(legacy_job_info["result"])

    if artifact_name == JOB_INFO_TRANSPILE_RESULT_PARAM:
        transpiled_code = legacy_job_info.get("transpiled_code")
        if transpiled_code in (None, ""):
            return None
        parsed = parse_payload(transpiled_code)
        if isinstance(parsed, dict):
            if any(
                key in parsed
                for key in ("transpiled_program", "stats", "virtual_physical_mapping")
            ):
                return parsed

            program_value = parsed.get("program")
            transpiled_program = None
            if isinstance(program_value, list):
                transpiled_program = program_value[0] if program_value else None
            elif program_value not in (None, ""):
                transpiled_program = program_value

            return {
                "transpiled_program": transpiled_program,
                "stats": parsed.get("stats"),
                "virtual_physical_mapping": parsed.get("virtual_physical_mapping"),
            }

        transpiled_program = parsed[0] if isinstance(parsed, list) and parsed else parsed
        return {
            "transpiled_program": transpiled_program,
            "stats": None,
            "virtual_physical_mapping": None,
        }

    return None


def load_external_payloads(
    args: argparse.Namespace, row: dict[str, Any], storage: AbstractStorage | None = None
) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    if args.legacy_sse_log_prefix:
        if storage is None:
            raise MigrationError(
                "storage is required when --legacy-sse-log-prefix is specified"
            )
        sse_log_payload = load_legacy_sse_log(args, storage, str(row["id"]))
        if sse_log_payload is not None:
            payloads[JOB_INFO_SSE_LOG_PARAM] = sse_log_payload
    return payloads


def load_legacy_sse_log(
    args: argparse.Namespace, storage: AbstractStorage, job_id: str
) -> Any | None:
    key_prefix = args.legacy_sse_log_prefix.rstrip("/")
    sidecar_key = (
        f"{key_prefix}/{args.legacy_sse_log_pattern.format(job_id=job_id)}"
        if key_prefix
        else args.legacy_sse_log_pattern.format(job_id=job_id)
    )
    sidecar_bytes = storage.get(sidecar_key)
    if sidecar_bytes is None:
        return None

    if sidecar_key.endswith(".zip"):
        with ZipFile(BytesIO(sidecar_bytes)) as zip_file:
            names = zip_file.namelist()
            if not names:
                raise MigrationError(f"legacy SSE log zip is empty: {sidecar_key}")
            return parse_payload(zip_file.read(names[0]))

    return parse_payload(sidecar_bytes)


def collect_non_input_keys() -> set[str]:
    excluded = {"message", "reason", "desc", "transpiled_code"}
    for artifact_name in OUTPUT_ARTIFACT_NAMES:
        excluded.update(ARTIFACT_ALIASES[artifact_name])
    return excluded


def parse_payload(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, bytes):
        value = value.decode()
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if stripped == "":
        return None

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(stripped)
        except Exception:
            continue
    return stripped


def coerce_json_text(value: Any) -> str:
    parsed = parse_payload(value)
    if parsed is None:
        return "{}"
    if isinstance(parsed, str):
        return parsed
    return json.dumps(parsed)


def normalize_job_type(job_type: str) -> str:
    normalized = job_type.lower()
    aliases = {
        "multiprogramming": "multi_manual",
        "multi": "multi_manual",
        "multi_manual": "multi_manual",
        "sampling": "sampling",
        "estimation": "estimation",
        "sse": "sse",
        "none": "none",
    }
    if normalized not in aliases:
        raise MigrationError(f"unsupported job_type: {job_type}")
    return aliases[normalized]


def artifact_key(job_id: str, artifact_name: str) -> str:
    return f"{job_id}/{artifact_name}.zip"


def put_zip(storage: Any, key: str, payload: Any) -> None:
    zip_bytes = build_zip_payload(payload, key)
    storage.put(key=key, data=zip_bytes)


def build_zip_payload(payload: Any, key: str) -> bytes:
    archive_name = build_archive_name(key)
    with BytesIO() as zip_buffer:
        with ZipFile(zip_buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
            zip_file.writestr(archive_name, json.dumps(payload))
        return zip_buffer.getvalue()


def build_archive_name(key: str) -> str:
    stem = Path(key).stem
    if stem == JOB_INFO_SSE_LOG_PARAM:
        return f"{stem}.log"
    return f"{stem}.json"


def parse_output_files(value: Any) -> list[str]:
    parsed = parse_payload(value)
    if parsed is None:
        return []
    if not isinstance(parsed, list):
        raise MigrationError(f"output_files must be a list, got {type(parsed).__name__}")
    return [str(item) for item in parsed]


def parse_datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise MigrationError(f"unsupported datetime value: {value!r}")


def coerce_optional_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def coerce_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


if __name__ == "__main__":
    raise SystemExit(main())
