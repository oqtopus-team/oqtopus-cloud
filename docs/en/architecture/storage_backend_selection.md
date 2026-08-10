# Storage Backend Selection

OQTOPUS keeps large job payloads in object storage (see [Quantum Jobs in Detail](quantum_jobs_in_detail.md) for the object layout and how the APIs use it). On AWS it uses the default `s3` driver, while on-premises deployments and local development run their own S3-compatible storage instead.

This page records why SeaweedFS was chosen for that role, and how the `seaweedfs` driver is configured.

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

`FSSpecStorage` reaches SeaweedFS through the same S3 code path as AWS S3, so no storage-layer code changes were needed. Credentials and the endpoint are configured via `STORAGE_SEAWEEDFS_BUCKET_NAME` / `STORAGE_SEAWEEDFS_USERNAME` / `STORAGE_SEAWEEDFS_PASSWORD` / `STORAGE_SEAWEEDFS_ENDPOINT_URL` in `backend/compose.yaml`. Any S3-compatible backend connects through that same code path, so switching to a different implementation later only means changing the connection settings.

### Upgrading from the MinIO setup

`make up` removes the stale `minio` container, but it does not migrate the
contents of the `minio-data` volume. Seed data is unaffected because `make up`
recreates it, but jobs you created yourself keep their database rows while their
objects become unreachable. To start clean, run `docker compose down -v` and then
`make up`. The `minio-data` volume is no longer managed by compose, so remove it
explicitly with `docker volume rm <project>_minio-data`.

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
