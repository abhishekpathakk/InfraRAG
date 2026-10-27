# Restore/Backup Runway-managed Cloud SQL

This document is meant for (1) disaster-recovery purposes or (2) change management issues with high risk of data corruption/loss (e.g. snapshot migration from an external Cloud SQL instance).

## Backup

All Runway-managed Cloud SQL instances will have periodic backups. These backups are tested daily
through [restore and data validation jobs](https://docs.runway.gitlab.com/managed_services/cloudsql/#restore-validation-1).

Service owners may want to manually create a backup before performing a critical data migration.
They may do so using a change management issue and enlisting the help from SREs.

[Creating manual backup](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/manage-standard-backups)

```
gcloud sql backups create --async --project PROJECT_NAME --instance=INSTANCE_NAME --description="<insert description here>"
```

[Listing existing backups](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/manage-standard-backups)

```
gcloud sql backups list --project PROJECT_NAME --instance INSTANCE_NAME
```

[Listing backups during outages](https://docs.cloud.google.com/sql/docs/mysql/backup-recovery/manage-standard-backups)

During an outage, you can only view backups for that instance using a wildcard (-) and grep for the instance.

```
gcloud sql backups list --project PROJECT_NAME --instance - | grep INSTANCE_NAME
```

## Restore

Restoring operations should be performed through a change management issue and approved by the engineer-on-call.

There are two ways to restore. **Start from the clone path.** The in-place restore is a last resort
because it destroys data.

| | Clone to a new instance | In-place restore from backup |
| --- | --- | --- |
| Command | `gcloud sql instances clone` | `gcloud sql backups restore` |
| Granularity | Any timestamp within the PITR window | Only the moment a backup was taken |
| Effect on production | None — production keeps running | Overwrites production data |
| Reversible | Yes | **No** |

Pick the in-place restore **only** when no current data is worth keeping. If any writes since the
recovery point still matter, use the clone path — an in-place restore discards them.

### Default path: clone to a new instance

This creates a new instance from a point in time. Production is untouched, so it is safe to run
while you are still working out what went wrong.

Confirm the most recent point you can recover to. The oldest is bounded by the instance's
`transaction_log_retention_days` and `retained_backups_count`:

```
gcloud sql instances get-latest-recovery-time --instance=SOURCE_INSTANCE --project=PROJECT_NAME
```

Create the clone:

```
gcloud sql instances clone SOURCE_INSTANCE TARGET_INSTANCE \
  --project=PROJECT_NAME \
  --point-in-time 'POINT_IN_TIME'
```

> **Note:** `POINT_IN_TIME` is an RFC 3339 timestamp in UTC. For example,
> `2026-08-20T14:00:00.000Z` for 14:00 UTC on 20 August 2026. The value must fall inside the
> recovery window confirmed above.

Omitting `--point-in-time` clones the source's **current consistent state** — note that if the data
is already damaged, you get the damage back.

The clone is a **new instance** with a new instance connection name and its own PSC service
attachment, but no consumer endpoint, DNS record or IAM bindings — those are keyed to the instance
name in the Runway provisioner. It exists, but nothing can reach it yet.

What happens next depends on why you cloned:

- **Extract & retire** — pull the lost data out of the clone, put it back into production, then tear
  the clone down.
- **Cutover & keep** — promote the clone to be the production instance by importing it into Runway,
  which then provisions its network, IAM, alerting and monitoring.

> **Both procedures are still in development and are not documented yet.** Until they are, stop
> after the clone and engage DBRE and `#g_runway` to complete the recovery. The clone itself is safe
> and buys time — nothing is lost by creating it while you get help.

### Last resort: in-place restore from backup

> **This is destructive and cannot be undone.** It overwrites all data on the target instance, and
> **every write between the backup and the restore is permanently lost**. It also restarts the
> instance and drops existing connections. Only use it when no current data is worth keeping.

Find the backup to restore from:

```
gcloud sql backups list --project PROJECT_NAME --instance INSTANCE_NAME
```

Restore it:

```
gcloud sql backups restore BACKUP_ID --project PROJECT_NAME --restore-instance=INSTANCE_NAME
```

> **After the restore, the instance's backup configuration is reset to Google defaults**, which can
> leave point-in-time recovery switched off. If that is not corrected, the clone path above stops
> working — you cannot clone to a timestamp on an instance with no transaction logs. The
> reconciliation procedure is not defined yet, so engage `@dbre` at `#g_database_operations`
> and `#g_runway` before closing the change management issue.
