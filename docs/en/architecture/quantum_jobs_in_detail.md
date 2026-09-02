# Quantum Jobs in Detail

OQTOPUS stores large quantum-job payloads in object storage and keeps only job metadata in the database.
The User API, Provider API, and storage service are connected by presigned URLs, so clients upload and download job files directly without sending large payloads through the API server.

This page describes the current backend behavior and the storage conventions used by the surrounding clients. It intentionally follows the running backend implementation and OpenAPI files under `backend/oas`.

## Storage Model

Each job owns a storage prefix named by its job ID:

```text
<job_id>/input.zip
<job_id>/combined_program.zip
<job_id>/transpile_result.zip
<job_id>/result.zip
<job_id>/sse_log.zip
```

The supported `.zip` object names are fixed by the backend. Each zip conventionally contains a single payload file, but the backend validates the object key, not the filename inside the archive:

| Object | Conventional archive entry name | Producer | Consumer | Payload format | Notes |
| --- | --- | --- | --- | --- | --- |
| `input.zip` | `input.json` | User | Provider, User | JSON matching the User API `jobs.S3SubmitJobInfo` | Required before submission can be completed. |
| `combined_program.zip` | `combined_program.json` | Provider | User | JSON payload for the combined program | Only accepted for `multi_manual` jobs. |
| `transpile_result.zip` | `transpile_result.json` | Provider | User | JSON matching `jobs.S3TranspileResult` | Transpilation output. |
| `result.zip` | `result.json` | Provider | User | JSON matching `jobs.S3JobResult` | Job result. |
| `sse_log.zip` | `sse_log.log` | Provider | User | JSON string payload containing the SSE log text | Only accepted for `sse` jobs. |

The default storage driver is S3. Self-hosted deployments and local development can use `local` or `seaweedfs` — the deprecated `local:minio` is still accepted — but the API contract is the same: the API returns upload presigned URL data or download presigned URLs, and the client transfers files directly to the storage backend.

For the current storage-backed format, client-side archive entries conventionally use `<object-stem>.json`, except SSE logs, which conventionally use a `.log` entry.

For why the `seaweedfs` driver used by local development and on-premises deployments was chosen, and how it is configured, see [Storage Backend Selection](storage_backend_selection.md).

## User API Flow

1. Register a job with `POST /jobs`.
   The backend creates a DB row in `registered` status with a generated `job_id` and returns an upload presigned URL for `<job_id>/input.zip`.
2. Upload `input.zip` to the returned presigned URL.
   The uploaded zip conventionally contains the job input as `input.json`, described by the User API `jobs.S3SubmitJobInfo`.
3. Complete submission with `POST /jobs/{job_id}/submit`.
   The request body contains DB metadata such as `device_id`, `job_type`, `shots`, and optional transpiler, simulator, mitigation, name, and description fields. The backend verifies that `<job_id>/input.zip` exists before moving the job to `submitted`.
4. Read job details with `GET /jobs` or `GET /jobs/{job_id}`.
   For submitted and later jobs, `job_info.input` is a download presigned URL. Uploaded provider outputs appear in `job_info` after the provider reports them through `PATCH /jobs/{job_id}/status`.
5. Delete a terminal job with `DELETE /jobs/{job_id}`.
   Deletion is allowed only for `succeeded`, `failed`, and `cancelled` jobs. The backend deletes the DB row and all objects under `<job_id>/`.

`registered` jobs are visible to the owner, but their DB row contains placeholder values for fields that are not known until submission. User responses therefore expose only `job_id` and `status` for registered jobs unless a filtered field is explicitly requested, in which case undefined fields are returned as `null`.

## Provider API Flow

1. Poll jobs with `GET /jobs?device_id=<device_id>`.
   Registered jobs are excluded. When the provider fetches a `submitted` job, the backend advances it to `ready` and returns `input`, a download presigned URL for `<job_id>/input.zip`.
2. Optionally request output upload URLs with `GET /jobs/{job_id}/upload?items=...`.
   `items` is a comma-separated list from `combined_program`, `transpile_result`, `result`, and `sse_log`. The backend rejects `combined_program` for non-`multi_manual` jobs and rejects `sse_log` for non-`sse` jobs.
3. Mark execution as started with `PATCH /jobs/{job_id}/status` and body `{ "status": "running" }`.
   This transition is allowed only from `ready`.
4. Upload output files directly to storage using the presigned URL data.
5. Complete the job with `PATCH /jobs/{job_id}/status`.
   Final statuses are `succeeded`, `failed`, and `cancelled`. The request can include `execution_time`, `message`, and `output_files`.

`output_files` must contain full storage keys such as `<job_id>/result.zip`. The backend validates that each key belongs to the patched job, has one of the supported file names, and exists in storage. The database stores the normalized object names without the job ID or `.zip` suffix, and the User API later expands them into `job_info` download URLs.

## Status Transitions

The current provider status transitions are:

| From | To | Actor |
| --- | --- | --- |
| `registered` | `submitted` | User API `POST /jobs/{job_id}/submit` |
| `submitted` | `ready` | Provider API `GET /jobs` |
| `ready` | `running` | Provider API `PATCH /jobs/{job_id}/status` |
| `ready` | `failed` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `succeeded` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `failed` | Provider API `PATCH /jobs/{job_id}/status` |
| `running` | `cancelled` | Provider API `PATCH /jobs/{job_id}/status` |
| `registered`, `submitted`, `ready`, `running` | `cancelled` | User API `POST /jobs/{job_id}/cancel` |

The `ready -> failed` transition is supported so that provider-side preprocessing failures can be reported before execution starts.

## Job Input and Output Schemas

`input.zip` conventionally contains `input.json`, and that payload matches the User API `jobs.S3SubmitJobInfo`.

| Field | Required for | Notes |
| --- | --- | --- |
| `program` | `sampling`, `estimation`, `multi_manual` | Array of OpenQASM 3 programs. Non-multiprogramming jobs normally contain one program. |
| `operator` | `estimation` | Array of Pauli operator items. |

The Provider API has a separate generated `jobs.S3SubmitJobInfo` schema that includes `sse_program` for SSE jobs. That field is not part of the User API input-upload schema described here.

For provider output zip files and the conventional payload names/schema inside them, refer to the storage-model table above.

Example archive layouts:

```text
<job_id>/input.zip
  input.json

<job_id>/result.zip
  result.json

<job_id>/transpile_result.zip
  transpile_result.json

<job_id>/sse_log.zip
  sse_log.log
```

## Implementation Notes

- `jobs.job_info` is no longer a DB column. The `jobs` table stores metadata, `output_files`, and `message`.
- User-facing `job_info` is a response object containing presigned download URLs and the provider message, not an inline serialized JSON payload.
- Upload presigned URLs expire according to the storage strategy; the current default in `FSSpecStorage` is one hour.
- S3 object cleanup is best-effort after the DB row is deleted. If storage cleanup fails, the API returns an internal server error.
