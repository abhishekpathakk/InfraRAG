# Topology Service Database Restore Runbook

## Overview

This runbook describes how to restore the Topology Service database from a Cloud Spanner backup. The Topology Service uses Cloud Spanner as its underlying database. Restores are performed using the `spanner-restore.sh` script in the [Topology Service deployer repository](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer), which finds the latest backup, copies it to the target environment/instance, and restores it as a new database.

---

## Prerequisites

Before running the script, ensure the following:

- Request and Verify IAM permissions for spanner operation using project [breakglass](breakglass.md) request.
- Ensure **gcloud CLI** is installed and authenticated (`gcloud auth login` / `gcloud auth application-default login`)
- You have the following IAM roles on **both** source and destination projects:
  - `roles/spanner.backupAdmin`
  - `roles/spanner.databaseAdmin`
- The destination Spanner instance already exists

> ⚠️ If you are restoring due to an active incident, ensure this runbook is being followed in coordination with the on-call engineer and that the incident channel is kept up to date.

---

## Steps

### 1. Create a New Spanner Instance via Terraform

Update the Terraform configuration in the [Topology Service deployer repository](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer) to define a new Spanner instance to restore into. See the [example MR](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer/-/merge_requests/155) for reference.

Rather than restoring into the existing instance, this creates a new adjacent dedicated instance for restore. This ensures there is no risk of interfering with the currently running database during the restore process.

### 2. Review and Approve the Terraform Plan

Before applying, review the generated Terraform plan report carefully:

- Confirm it is **only adding** new resources for the new instance
- Confirm it is **not deleting or modifying** any existing resources
- Get the plan approved by a reviewer before proceeding

### 3. Run the Restore Script

Once the destination instance is ready, run the restore script from the Topology Service deployer repository:

```bash
./scripts/spanner-restore.sh <SOURCE_PROJECT> <SOURCE_INSTANCE> <SOURCE_DATABASE> \
  <DEST_PROJECT> <DEST_INSTANCE> <DEST_DATABASE>
```

#### Arguments

| Argument | Description |
| --- | --- |
| `SOURCE_PROJECT` | GCP project ID containing the source Topology Service Spanner instance |
| `SOURCE_INSTANCE` | Source Spanner instance ID |
| `SOURCE_DATABASE` | Topology Service database ID to restore from |
| `DEST_PROJECT` | GCP project ID of the target environment |
| `DEST_INSTANCE` | Destination Spanner instance ID (the one created in Step 1) |
| `DEST_DATABASE` | Name for the restored database — use a descriptive name that includes a version or date (e.g. `topology-db-v2`) |

#### Example

```bash
./scripts/spanner-restore.sh \
  topology-prod topology-prod-instance-v1 topology-db-v1 \
  topology-prod topology-prod-instance-v2 topology-db-v2
```

### 4. Confirm the Restore Prompt

The script will display a summary of the source and destination details before proceeding. Review this carefully and enter `y` to confirm.

```
🔍 Looking up latest backup for database 'topology-db-v1'...

🗄️  Cloud Spanner Restore
   ┌─ Source ──────────────────────────────────
   │  Project  : topology-prod
   │  Instance : topology-prod-instance-v1
   │  Database : topology-db-v1
   │  Backup   : topology-db-backup-84936129
   ├─ Destination ─────────────────────────────
   │  Project  : topology-prod
   │  Instance : topology-prod-instance-v2
   │  Database : topology-db-v2
   └───────────────────────────────────────────

⚠️  Proceed with restore? This may overwrite existing data. [y/N]
```

### 5. Monitor the Output

The script polls every 15 seconds during the backup copy phase. Once the copy reaches `READY` state, the restore will begin automatically.

#### Expected Output

```
📦 Copying backup to destination project...
⏳ Waiting for backup copy to complete...
   ... still copying (state: CREATING)
✅ Backup copy complete

🚀 Starting restore operation...
✅ Restore complete: topology-prod/topology-prod-instance-v2/topology-db-v2
```

### 6. Verify the Restored Database

Once the script completes, confirm the restored database is healthy:

```bash
gcloud spanner databases describe <DEST_DATABASE> \
  --instance=<DEST_INSTANCE> \
  --project=<DEST_PROJECT>
```

### 7. Import the Restored Database into Terraform State

The restored database was created outside of Terraform, so it needs to be imported into the Terraform state to bring it under management. Run the following:

```bash
terraform -chdir="<path>/<to>/<terraform-env>" import \
  module.spanner_database_v2.google_spanner_database.database \
  projects/<project>/instances/<instance>/databases/<database>
```

Replace the placeholders with the actual project, instance, and database values used in the restore.

### 8. Point the Topology Service at the Restored Database

Updating the Topology Service configuration to use the new database is a **manual step** not handled by the script.
Update the relevant environment configuration for [grpc](https://gitlab.com/gitlab-com/gl-infra/cells/topology-service-deployer/-/blob/main/.runway/topology-rest/env-staging.yml#L59)
and [rest](https://gitlab.com/gitlab-com/gl-infra/cells/topology-service-deployer/-/blob/main/.runway/topology-rest/env-staging.yml#L59) request in
to point the service at the restored database and coordinate with the team before switching any traffic.

---

## Troubleshooting

| Error | Likely Cause | Resolution |
| --- | --- | --- |
| `❌ No backups found` | No backups exist for the Topology Service database, or the database name is incorrect | Verify the database name and list backups manually: `gcloud spanner backups list --project=<PROJECT> --instance=<INSTANCE>` |
| `❌ gcloud CLI not found` | gcloud is not installed or not on PATH | Install the [Google Cloud SDK](https://docs.cloud.google.com/sdk/docs/install-sdk) |
| `❌ Backup copy failed or entered unexpected state` | Copy operation failed in GCP | Check the GCP console for error details; verify IAM permissions and quota limits |
| Permission denied | Missing IAM roles | Ensure `roles/spanner.backupAdmin` and `roles/spanner.databaseAdmin` are granted on both projects |
| Destination database already exists | A database with the same name exists in the destination instance | Use a different `DEST_DATABASE` name or remove the existing one if safe to do so |

---

## Important Notes

- The script always restores from the **latest** backup. If you need to restore from a specific point in time, identify the correct backup manually using `gcloud spanner backups list` before running the script.
- The copied backup is retained for **7 days** in the destination project before expiring.
- The restored database must be **imported into Terraform state** after the restore (Step 7), otherwise Terraform may attempt to delete or recreate it on the next apply.
- Pointing the Topology Service at the restored database is a **manual step** coordinate with the team before switching traffic.

---

## Related Resources

- [Topology Service deployer repository](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer)
- [Cloud Spanner Backup & Restore docs](https://docs.cloud.google.com/spanner/docs/backup)
