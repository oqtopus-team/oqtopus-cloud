# Device Info in Detail

OQTOPUS stores device calibration payloads in object storage and exposes them through presigned URLs instead of returning inline JSON from the API.
The database keeps device metadata such as `device_type`, `status`, `n_qubits`, and `calibrated_at`, while the actual `device_info` payload lives in a storage-backed archive.

This page describes the current backend behavior and the storage conventions used by the surrounding clients. It follows the running implementation and OpenAPI files under `backend/oas`.

## Storage Model

Each device owns a deterministic storage key:

```text
devices/<device_id>/device_info.zip
```

The object key is fixed by the backend. Clients conventionally upload a zip containing a single `device_info.json` entry, but the backend validates the object key, not the filename inside the archive.

| Object | Conventional archive entry name | Producer | Consumer | Payload format | Notes |
| --- | --- | --- | --- | --- | --- |
| `devices/<device_id>/device_info.zip` | `device_info.json` | Admin client, Provider, Engine | Admin, User, SDKs | Device JSON payload | The only storage-backed device payload currently supported. |

The default storage driver is S3. Local development can use `local` or `local:minio`, but the API contract is the same: the API returns upload presigned URL data or download presigned URLs, and clients transfer the archive directly to the storage backend.

At the OpenAPI level, the payload format inside `device_info.zip` is not defined as a structured schema. Admin-side request models treat `device_info` as a JSON string, while read-side APIs expose `device_info` as a string field containing a presigned download URL.

## Read Model

`GET /devices` and `GET /devices/{device_id}` in both the Admin API and User API return `device_info` as a download presigned URL when `devices/<device_id>/device_info.zip` exists.
If the object does not exist, `device_info` is `null` even when the device row itself exists.

The backend does not store the storage key in the `devices` table. It reconstructs the key from `device_id` every time by using the fixed `devices/<device_id>/device_info.zip` convention.

## Database Specification

The `devices` table stores metadata for the current device state. The actual `device_info` payload is not stored in the database; it is stored under the current storage key derived from `device_id`.

| Column | Purpose |
| --- | --- |
| `id` | Device identifier. Also used as `<device_id>` in the current storage key `devices/<device_id>/device_info.zip`. |
| `device_type` | `QPU` or `simulator`. |
| `status` | Device availability state. |
| `n_qubits` | Qubit count shown for the current device row. |
| `basis_gates` | JSON-serialized basis gate list. |
| `instructions` | JSON-serialized supported instruction list. |
| `calibrated_at` | Timestamp at which the current `device_info` was confirmed. Updated when the Provider API confirms device_info. |
| `description` | Device description. |

The `device_info_history` table stores only the metadata needed to look up historical `device_info` snapshots. Historical payloads are not stored in the database either; they are stored under a deterministic history storage key derived from `device_id` and `calibrated_at`.

| Column | Type | Nullable | Purpose |
| --- | --- | --- | --- |
| `id` | integer / MySQL unsigned BIGINT | no | Surrogate primary key. |
| `device_id` | varchar(64) | no | Foreign key to `devices.id` with `ON DELETE CASCADE`. |
| `calibrated_at` | timestamp / datetime | no | Snapshot timestamp. Also part of the history storage key. |
| `n_qubits` | integer | no | Qubit count at the snapshot. Used by history lists and historical detail headers. |
| `n_couplings` | integer | no | Coupling count at the snapshot. Used by history lists and historical detail headers. |
| `created_at` | timestamp / datetime | yes | Row creation timestamp. |
| `updated_at` | timestamp / datetime | yes | Row update timestamp. On MySQL this uses `ON UPDATE CURRENT_TIMESTAMP`. |

Constraints and indexes are:

| Name | Definition |
| --- | --- |
| Primary key | `id` |
| Foreign key | `device_id` references `devices(id)` with `ON DELETE CASCADE` |
| Unique constraint | `(device_id, calibrated_at)`. A device can have only one snapshot for the same calibrated timestamp. |
| Index | `(device_id, calibrated_at)`. Used for history listing and "latest snapshot at or before timestamp" lookups. |

`device_info_history` intentionally does not have a `storage_key` column. The history object key is uniquely determined by this convention, so storing it again in the database would duplicate derived data:

```text
devices/<device_id>/history/<calibrated_at in UTC YYYYMMDDTHHMMSSffffffZ>/device_info.zip
```

The implementation generates this key with `get_device_info_history_key(device_id, calibrated_at)`. The relationship between a database row and a storage object is represented by `(device_id, calibrated_at)`, and read APIs derive the key when checking object existence and issuing presigned URLs.

`PATCH /devices/{device_id}/device_info` on the Provider API stores the uploaded archive under both the current key and the history key, updates `devices.calibrated_at`, and inserts a `device_info_history` metadata row. If the same `(device_id, calibrated_at)` already exists, the request is treated as a conflict and the history row is not overwritten.

`DELETE /devices/{device_id}` on the Admin API deletes the `devices` row, which cascade-deletes `device_info_history` rows. It also deletes the current object and each history object so neither the database nor object storage is left with orphaned device_info data.

## Admin API Flow

The current Admin API is a two-step storage-backed flow:

1. Register or update the device row in the database.
   `POST /devices` creates the row, and `PATCH /devices/{device_id}` updates DB-backed metadata such as `status`, `n_qubits`, and `description`.
2. Request an upload target with `GET /devices/{device_id}/device_info/upload`.
   The backend returns presigned URL data for `devices/<device_id>/device_info.zip`.
3. Upload `device_info.zip` directly to storage.
4. Optionally send `PATCH /devices/{device_id}` for any remaining DB-backed metadata such as `calibrated_at` or `description`.
   The uploaded `device_info.zip` itself is already the source of truth for subsequent reads, so the admin client does not need to echo `device_info` back in the PATCH body.

The current admin frontend uploads `device_info.zip` first and then PATCHes only the DB-backed fields that still need to change.

For backward compatibility, `POST /devices` still derives `device_id` from the inline `device_info` JSON in the request body. However, the inline JSON itself is not persisted as the read-model source of truth. After registration, API responses expose only the storage-backed object URL.

The update sequence is short, but the final API step differs between the Admin flow and the Provider/Engine flow:

```mermaid
sequenceDiagram
   participant Client as Admin or Engine
   participant API as Cloud API
   participant Storage as Object Storage

   Client->>API: GET /devices/{id}/device_info/upload
   API-->>Client: presigned upload URL data
   Client->>Storage: upload device_info.zip
   alt Admin flow
      Client->>API: PATCH /devices/{id} with remaining DB fields only
   else Provider or Engine flow
      Client->>API: PATCH /devices/{id}/device_info with calibrated_at
   end
   API-->>Client: update accepted
```

## Provider and Engine Flow

Provider-side uploads follow the same storage convention but use a dedicated confirmation endpoint:

1. Request an upload target with `GET /devices/{device_id}/device_info/upload` on the Provider API.
2. Upload `device_info.zip` directly to storage.
3. Confirm the upload with `PATCH /devices/{device_id}/device_info` and a `calibrated_at` timestamp.

The engine uses this flow through the provider API. On startup, `DeviceGatewayFetcher` performs an initial fetch from the device gateway and calls the device repository update sequence. If device-info updates are enabled, the repository:

1. requests a presigned upload target,
2. uploads `devices/<device_id>/device_info.zip`,
3. calls `PATCH /devices/{device_id}/device_info` with `calibrated_at`.

After startup, the same upload flow runs again whenever the fetched `device_info` payload or `calibrated_at` changes.

## Overwrite and Delete Semantics

Because the storage key is deterministic, uploading a new archive for the same `device_id` overwrites the previous object. The latest successful upload becomes the new source of truth.

`DELETE /devices/{device_id}` in the Admin API removes both:

- the database row in `devices`, and
- the storage object `devices/<device_id>/device_info.zip` if it exists.

This keeps device cleanup from leaving orphaned storage objects behind.

## Example Archive Layout

```text
devices/qulacs/device_info.zip
  device_info.json
```

## Implementation Notes

- `device_info` is storage-backed on reads. API responses expose a download presigned URL, not the raw JSON payload.
- The OpenAPI files do not define a typed schema for the contents of `device_info` itself. The write-side contract is effectively "JSON serialized into a string", and the read-side contract is "string URL to the archived payload".
- The Admin API PATCH contract is metadata-only. The current admin client uploads `device_info.zip` separately and does not send `device_info` back in `PATCH /devices/{device_id}`.
- `calibrated_at` remains in the `devices` table and is updated separately from the object upload confirmation.
- Upload presigned URLs expire according to the storage strategy; the current default in `FSSpecStorage` is one hour.
- The backend validates object existence, not the archive entry name inside `device_info.zip`.
- Recreating a device row does not recreate `device_info.zip`; a provider/admin upload or an engine startup sync is required to restore the object.
