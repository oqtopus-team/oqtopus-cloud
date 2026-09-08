# Storage Backend Selection

OQTOPUS keeps large job payloads in object storage (see [Quantum Jobs in Detail](quantum_jobs_in_detail.md) for the object layout and how the APIs use it). On AWS it uses the default `s3` driver, while on-premises deployments and local development run their own S3-compatible storage instead.

SeaweedFS is added as the default local backend. The existing `local:minio` driver and its configuration remain supported, with a deprecation warning. This page records the selection, configuration, and release compatibility checks.

## Selection criteria

The backend used to be MinIO, but MinIO's OSS edition was effectively discontinued in 2026 (the Community Edition lost its admin console, pre-built Docker images stopped being published, and the project was eventually archived), so a replacement was needed. Candidates were compared against the following criteria.

1. S3-compatible API (list/get/put, plus upload/download via presigned URLs)
2. Can start on a single server, but also supports clustering
3. Has a management web UI
4. Ships an official Docker image
5. Active, open development community (i.e. won't end up like MinIO)
6. Production-grade

Must also be free of charge.

| Candidate | ①S3-compatible | ②Single→cluster | ③Web UI | ④Official Docker | ⑤Active OSS (who runs it) | ⑥Production track record | Verified locally | Free | Verdict |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | --- |
| **[SeaweedFS](https://github.com/seaweedfs/seaweedfs)** | ○ | ○ | ○ | ○ | △ Individual (Chris Lu) | ○ Proven | ○ | ○ | **◎ Adopted** |
| [RustFS](https://github.com/rustfs/rustfs) | ○ | △ | ○ | ○ | △ Company (RustFS Inc., young) | △ Still beta | ○ | ○ | ○ Passed over for now (capable, but still beta as of `v1.0.0-beta.12` and clustering only landed recently) |
| [Garage](https://garagehq.deuxfleurs.fr/) | ○ | ○ | × | ○ | ◎ Non-profit (Deuxfleurs) | ○ | - Not tested | ○ | ○ Runner-up (no web UI) |
| [Ceph (RGW)](https://docs.ceph.com/en/latest/radosgw/) | ◎ | × | ○ | ○ | ◎ Multiple large vendors (Red Hat/IBM/SUSE) | ◎ | - Not tested | ○ | △ Overkill (requires a minimum of 3 nodes) |
| [Cloudflare R2](https://developers.cloudflare.com/r2/) | ○ | - | - | - | - | - | - | - | ✕ Excluded (cannot be self-hosted; managed service that only runs on Cloudflare) |
| ~~[MinIO](https://github.com/minio/minio)~~ | ○ | ○ | ~~×~~ | ~~×~~ | ~~× Company (MinIO Inc., changed direction)~~ | ○ | - | ~~△~~ | ✕ Excluded (archived in 2026) |

SeaweedFS is also driven mainly by a single individual, so the ⑤ single-maintainer risk does not fully go away. It was still adopted because it beat the other candidates on track record, feature coverage, and the local verification results.

## The seaweedfs driver

The `seaweedfs` driver stores objects in [SeaweedFS](https://github.com/seaweedfs/seaweedfs), which `backend/compose.yaml` starts for local development and which on-premises deployments run in place of AWS S3.

`FSSpecStorage` reaches SeaweedFS through the same S3 code path as AWS S3, with directory markers excluded from prefix results so empty SeaweedFS directories are not exposed as object keys. Credentials and the endpoint are configured via `STORAGE_SEAWEEDFS_BUCKET_NAME` / `STORAGE_SEAWEEDFS_USERNAME` / `STORAGE_SEAWEEDFS_PASSWORD` / `STORAGE_SEAWEEDFS_ENDPOINT_URL` in `backend/compose.yaml`. Any S3-compatible backend connects through that same code path, so switching to a different implementation later only means changing the connection settings. The driver name records the backend this project runs and verifies against; nothing in the driver is specific to SeaweedFS. Another self-hosted S3-compatible backend, RustFS for example, is reached by pointing `STORAGE_SEAWEEDFS_ENDPOINT_URL` and the credentials at it.

### Migrating from `local:minio`

The `local:minio` driver is deprecated but still works: its settings are read exactly as before, and it logs a warning on every use. To migrate, set `STORAGE_DRIVER` to `seaweedfs` and rename the `STORAGE_LOCAL_MINIO_*` settings to `STORAGE_SEAWEEDFS_*`; in Terraform, `storage_env_vars_local_minio` becomes `storage_env_vars_seaweedfs`.

No removal date is set. Removing `local:minio` is a separate compatibility-policy decision that must account for existing deployments and their migration. Passing the SeaweedFS compatibility tests does not authorize removal or mean that users have migrated.

### Running the deprecated MinIO stack locally

`backend/compose.yaml` still carries the MinIO services, behind a compose profile so nothing starts them unless they are asked for. This keeps existing configurations runnable and allows regression and compatibility checks while the driver remains supported.

```bash
cd backend
make up STORAGE_STACK=minio                   # MySQL + MinIO, migrations and seed data
make run-user STORAGE_STACK=minio             # run an API against it
make check-presigned-post STORAGE_STACK=minio # same storage check as seaweedfs
```

`STORAGE_STACK` defaults to `seaweedfs`, and the two stacks bind the same host ports, so run one at a time. The `user-api` / `provider-api` services in `compose.yaml` are wired to SeaweedFS, so run the APIs on the host for this stack — which is the documented development flow anyway. MinIO is archived and receives no further fixes: this is for verifying the deprecated driver locally, nothing else.

## Release compatibility check

To verify compatibility with `local:minio`, run the following test in the release introducing SeaweedFS and confirm that both backends pass. Decide when to remove `local:minio` separately.

```bash
cd backend
make test-storage-compatibility
```

The test starts and stops dedicated SeaweedFS and MinIO services and checks reads, writes, deletion, listing, and presigned uploads/downloads against the same expectations. Coverage is limited to storage operations; it does not include complete API workflows or migration of existing data.

Results and image identities are saved in `backend/storage-compatibility-results/`. Record the verification results in the PR.

## Verifying the storage path

A script is available for checking the storage after swapping the backend or updating its version. It is not needed for normal development.

With storage running through `make up`, it generates presigned POSTs through OQTOPUS Cloud, uploads objects concurrently, and reads every object back from storage to verify its contents. It deletes the test objects afterward.

```bash
cd backend
make check-presigned-post PRESIGNED_POST_COUNT=100 PRESIGNED_POST_WORKERS=20
```

This covers presigned URL generation, HTTP POST, and stored-object verification. It does not cover the entire API workflow from job registration through completion.

The same path can benchmark POST/GET throughput and per-request latency. The first round is excluded as a warmup, and every GET response is checked for matching content.

```bash
make benchmark-presigned-post \
  PRESIGNED_POST_LABEL=SeaweedFS \
  PRESIGNED_POST_COUNT=5000 \
  PRESIGNED_POST_WORKERS=50 \
  PRESIGNED_POST_PAYLOAD_BYTES=4096 \
  PRESIGNED_POST_ROUNDS=5 \
  PRESIGNED_POST_OUTPUT_JSON=benchmark-results/seaweedfs-4k.json
```

For large objects, for example, use `PRESIGNED_POST_COUNT=20`, `PRESIGNED_POST_WORKERS=10`, `PRESIGNED_POST_PAYLOAD_BYTES=104857600`, and `PRESIGNED_POST_ROUNDS=3`. Standard output contains a table with ops/s, MiB/s, p50, p95, p99, and errors. The JSON report also records individual rounds and the execution environment. GET reads objects immediately after POST in each round, so this is a warm workflow measurement similar to the OQTOPUS Cloud upload/download path rather than a cold-read benchmark.

### Measured results (as of 2026-08-05)

SeaweedFS and RustFS measured on the same host under the same conditions. Values are transfer rates. Across every run there were zero HTTP errors, zero missing objects, and zero content mismatches.

Small objects (4KiB, 5,000 objects, 50 workers, 5 rounds):

| Backend | POST | GET |
| --- | ---: | ---: |
| SeaweedFS | 2.11 MiB/s | 2.61 MiB/s |
| RustFS | 2.18 MiB/s (+3.5%) | 2.63 MiB/s (+0.9%) |

Large objects (100MiB, 20 objects, 10 workers, 3 rounds):

| Backend | POST | GET |
| --- | ---: | ---: |
| SeaweedFS | 209 MiB/s (+23%) | 81.5 MiB/s (+9%) |
| RustFS | 169 MiB/s | 75.1 MiB/s |

At 4KiB the two are effectively equal; at 100MiB SeaweedFS is 9–23% faster. Real workloads are dominated by payloads of a few KB, though, so performance was not the deciding factor in the selection.

The measurements were taken on Docker under WSL2 (14 vCPU / 15GiB RAM, local Docker volume). These numbers depend heavily on the hardware and on whatever else is running, so treat them as a like-for-like comparison rather than absolute figures.
