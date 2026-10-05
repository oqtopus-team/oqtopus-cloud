# Backup and Recovery

This page describes how OQTOPUS Cloud protects its stateful data from accidental loss, and how to recover it. Protection is layered: critical resources are hard to delete by accident (deletion protection), and if data is lost anyway it can be restored (backups / versioning).

## What is protected

| Resource | Deletion protection | Recovery mechanism |
| --- | --- | --- |
| Cognito user pools (user / admin) | `prevent_destroy` + Cognito deletion protection | Daily export to S3 (`cognito-backup` module) |
| RDS (MySQL) | `prevent_destroy` + RDS `deletion_protection` | Automated snapshots (5-day retention) |
| RDS storage KMS key | `prevent_destroy`, 30-day deletion window, key rotation | Protected in place (see note below) |
| S3 (job storage) | `prevent_destroy` | Versioning (noncurrent versions kept 7 days) |
| S3 (logging) | `prevent_destroy` | Lifecycle transitions / expiration |

> [!NOTE]
> A KMS key cannot be backed up or exported. It is protected in place instead. The RDS storage (and every snapshot) is encrypted with this key, so if the key is deleted the live database **and** all snapshots become permanently unrecoverable. The 30-day deletion window gives time to notice and cancel an accidental key-deletion request.

## Deletion protection

Stateful resources use Terraform's `lifecycle { prevent_destroy = true }`, which blocks any Terraform-driven destroy until the block is explicitly removed. The scope differs per resource:

- **Cognito, RDS** — the resource-side deletion-protection flag additionally blocks deletion via the AWS console / API.
- **RDS storage KMS key** — cannot be deleted instantly: AWS KMS always enforces a 7–30 day waiting period (default 30) before a key is destroyed, so a deletion can be cancelled during that window. Terraform is configured to use a 30-day window. (Guaranteeing the full 30 days for every caller would additionally require a key-policy condition on `kms:ScheduleKeyDeletion`.)
- **S3 buckets** — `prevent_destroy` guards only the Terraform path. A console / API deletion is still possible, so reviewing `terraform plan` and normal IAM restrictions remain the safeguards there.

To intentionally delete a protected resource (for example, when decommissioning an environment):

1. Remove (or comment out) the `prevent_destroy` block, and for Cognito / RDS set the AWS-side deletion-protection flag to `false`. Run `terraform apply` — this only lifts the protection, it does not delete anything yet.
2. Then run the destroy (a second `terraform apply` / `terraform destroy`) and confirm the plan shows **only** the intended destroy.

> [!NOTE]
> Disabling AWS-side deletion protection and destroying in a *single* apply fails, because the delete is attempted while protection is still active. Lift the protection in one apply, then destroy in the next.

> [!IMPORTANT]
> Always review the output of `terraform plan` before `apply`. If the plan contains an unexpected destroy or replace, stop and investigate.

## Backups

### Cognito — daily export

The `cognito-backup` Terraform module provisions an EventBridge-scheduled Lambda that runs once a day and exports every user and group of the configured user pools to a dedicated, private, encrypted S3 bucket as JSON (`{pool_id}/{timestamp}-{run_id}.json`). Each pool is exported independently, so one pool failing does not skip the others, and the invocation is still marked failed so it can be alarmed on. Backups are retained for `backup_retention_days` (default: 30 days).

> [!NOTE]
> Cognito does not expose passwords or MFA/TOTP secrets. A restore therefore requires re-importing users, forcing a password reset, having any MFA-enabled users (e.g. the admin pool) re-register their MFA device, and remapping each username to its **new** `sub` in the RDS `users.cognito_id` column (re-imported users receive a new `sub`). The CSV import tool also does not carry account state, so any disabled (`Enabled=false`) user must be disabled again (`AdminDisableUser`) after import.

### RDS — automated snapshots

RDS automated backups are enabled with a 5-day retention (`backup_retention_period`). Restoring creates a new instance from a snapshot; the storage KMS key must still exist for the snapshot to be decrypted. If a longer recovery window is required, increase `backup_retention_period` (this increases snapshot storage cost).

### S3 — versioning

The job-storage bucket has versioning enabled. A lifecycle rule expires noncurrent versions 7 days after they are superseded or deleted, so an accidental overwrite or delete can be recovered within that window while storage stays bounded. Time-based expiry is used (rather than a version-count cap) so that the data of deleted objects is actually purged after 7 days instead of lingering forever as the last retained version. (Delete markers may remain afterwards; each is billed only for the length of its object key name, i.e. negligible.)

## Recovery quick reference

> [!NOTE]
> These are summaries, not a complete runbook. A full, rehearsed restore procedure — covering UNCONFIRMED / disabled users, `sub` remapping, and reconciliation with existing RDS rows — should be established and tested before it is needed.

- **Accidentally overwritten / deleted job object (within 7 days)** — restore the previous version from the job-storage bucket's version history (S3 console or `aws s3api list-object-versions` / `get-object --version-id`).
- **Cognito user pool damaged / users lost** — take the latest export from the backup bucket and follow the restore caveats above (re-import, password reset, MFA re-registration, `sub` remap).
- **RDS data loss** — restore from an automated snapshot (point-in-time restore), then repoint the application. Ensure the storage KMS key is intact.

## Retention and cost summary

| Backup | Retention | Cost |
| --- | --- | --- |
| Cognito daily export | 30 days (configurable) | Negligible (a few MB/day of JSON) |
| S3 job-bucket versioning | 7 days of noncurrent versions | Bounded to ~7 days of overwritten/deleted object volume |
| RDS automated snapshots | 5 days | Snapshot storage (scales with DB size) |
