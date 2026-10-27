# PatroniPrimaryDiskIOSaturated

## Overview

The data volume on a Patroni **primary** is queueing IO requests *and* each request is slow.
Both conditions have held for 3 minutes.

This is a leading indicator. When it fires the database is still serving traffic, and you have a
short window to act before the queue turns into application timeouts and HTTP 503s. Assume that
window is **minutes**: storage contention on the primary reaches users quickly, through pgbouncer
pool exhaustion.

**Work the workload first.** Most of the time something we are running is driving the disk. Do not
start by trying to prove the disk is broken — see [Is it the disk?](#4-is-it-the-disk) for why
that question is slow to answer.

## Scope

- **Primary only.** The alert joins on `pg_replication_is_replica == 0` and follows failovers.
- **The data volume only** — the device backing `/var/opt/gitlab`. The log device and the boot
  disk are out of scope: the log device is throughput-limited by design and saturates during
  normal operation, so it is excluded deliberately.
- Applies to every Patroni cluster: `patroni`, `patroni-ci`, `patroni-registry`, `patroni-sec`.

## Mental model

Two signals, doing two different jobs:

| Signal | Recording rule | What it means |
| --- | --- | --- |
| Queue depth (`aqu-sz`) | `patroni:disk_queue_depth:rate1m` | requests are backing up |
| Per-op wait (`await`) | `patroni:disk_await_seconds:rate1m` | each request is slow |

Depth alone means nothing on NVMe — deep queues are how it reaches its rated IOPS. A high depth
with normal `await` is healthy parallelism. It is the **combination** that indicates contention,
which is why the alert requires both.

Typical healthy values on these disks: `await` around 0.5–2ms, depth below 1–2. Thresholds are
set per cluster in
[`patroni-disk-io-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-disk-io-alerts.libsonnet).

## Diagnose

### 1. Confirm it, and find the node

Which node is primary:

```
sudo gitlab-patronictl list
```

On that node, identify the data device and watch it live:

```
df -h /var/opt/gitlab          # names the device, e.g. /dev/nvme1n1
iostat -xz 1 10
```

Read `aqu-sz` (older `sysstat` calls it `avgqu-sz`), `r_await` and `w_await` for that device only.
Ignore the log device — it is throughput-limited and noisy, and is not what fired this alert.

If `aqu-sz` is high but `await` is normal, this is healthy parallelism. Investigate the alert
thresholds, not the database.

### 2. Find what is generating the IO

Start with the **Postgres Wait sampling dashboard**. It is backed by `pg_wait_sampling` and shows
the workload queued behind each wait event, which is normally enough to name the culprit without
logging into the node.

[Postgres Wait sampling dashboard — IO waits](https://dashboards.gitlab.net/d/postgres-ai-NEW_postgres_ai_04/cfd803b?orgId=1&from=now-1h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-type=patroni&var-wait_type=IO&var-wait_event=$__all&var-Filters=)

Set the template variables to match the node from step 1:

| Variable | Value |
| --- | --- |
| `environment` | `gprd` |
| `type` | the cluster: `patroni`, `patroni-ci`, `patroni-registry` or `patroni-sec` |
| `fqdn` | the **primary** node |
| `wait_type` | `IO` |
| `wait_event` | all, unless you are chasing a specific event |

Getting `type` and `fqdn` right matters — the dashboard will happily show you a healthy replica.

#### If the dashboard has no data

Fall back to querying the primary directly:

```
sudo gitlab-psql
```

Longest-running non-idle queries:

```sql
SELECT pid, now() - xact_start AS xact_age, wait_event_type, wait_event, state,
       left(query, 200) AS query
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY xact_age DESC
LIMIT 20;
```

What is waiting on IO right now:

```sql
SELECT wait_event, count(*)
FROM pg_stat_activity
WHERE wait_event_type = 'IO'
GROUP BY 1 ORDER BY 2 DESC;
```

Autovacuum, a common source of sustained write IO:

```sql
SELECT pid, now() - xact_start AS age, left(query, 120) AS query
FROM pg_stat_activity
WHERE query LIKE 'autovacuum:%'
ORDER BY age DESC;
```

Top workload by endpoint, which usually names the culprit path. This is a Prometheus metric, so
run it in [Grafana Explore](https://dashboards.gitlab.net/explore) against the Mimir datasource,
not in psql:

```promql
sum by (endpoint, fqdn, environment) (
  avg_over_time(pg_stat_activity_marginalia_sampler_active_count{env="gprd", fqdn=~"patroni-.*"}[1m])
)
```

Check the kernel for stuck IO or device errors:

```
sudo journalctl -k --since "30 min ago" | grep -iE 'blocked for more than|I/O error|nvme|EXT4-fs error'
```

### 3. Check whether it has already reached users

Contention on the primary becomes an outage through pgbouncer, so **waiting clients** are the
signal that it has stopped being a leading indicator.

[pgbouncer Overview dashboard](https://dashboards.gitlab.net/d/postgresql-pgbouncer_overview/postgresql3a-pgbouncer-overview?orgId=1&from=now-3h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd)

Set `type` to the pgbouncer fleet in front of the affected cluster. It is multi-select, so select
several if you are not sure which side is affected. Include the Patroni cluster itself
(`patroni` / `patroni-ci`) as well — Sidekiq's replica-side pool runs on the Patroni nodes and
reports under those types.

**Do not assume Web/API traffic is the whole picture.** The top row splits the pools: use the
**(sidekiq)** panels as well as the **(web)** ones. A disk problem on the primary can show up as
queueing Sidekiq clients while the Web pools still look healthy — that delays background processing
rather than returning 503s, and it is easy to miss.

Watch **Waiting Client Connections** and **Max Wait**. Either one climbing means clients are
queueing for a server connection, which is the step between disk contention and user-facing 503s.
If they are rising, page `@dbre` in `#g_database_operations` and keep working the cause in
parallel — do not wait until you have a root cause.

The same state is available on the node itself:

```
for c in /usr/local/bin/pgb-console*; do $c -c 'SHOW POOLS;'; done
```

`cl_waiting` is the per-pool version of the same number.

### 4. Is it the disk?

Check what changed first — this explains most events:

- [production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name%5B%5D=change)
  and recent application deploys: a new unindexed query, a migration, a backfill, or a changed
  Sidekiq batch size
- a manual `VACUUM`, `REINDEX`, or backup verification started on the primary

If nothing explains it, check [Personal Service Health](https://console.cloud.google.com/servicehealth)
for a Compute Engine incident. That is more timely than the disk metric below.

#### GCP disk performance status

GCP publishes its own view of disk health:

```promql
stackdriver_gce_instance_compute_googleapis_com_instance_disk_performance_status{
  env="gprd",
  device_name=~"patroni.*",
  performance_status=~"Degraded|Severely Degraded"
} > 0
```

[Open in Explore](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22dzb%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22expr%22:%22%20%20stackdriver_gce_instance_compute_googleapis_com_instance_disk_performance_status%7B%5Cn%20%20%20%20env%3D%5C%22gprd%5C%22,%5Cn%20%20%20%20device_name%3D~%5C%22patroni.%2A%5C%22,%5Cn%20%20%20%20performance_status%3D~%5C%22Degraded%7CSeverely%20Degraded%5C%22%5Cn%20%20%7D%20%3E%200%22,%22format%22:%22time_series%22,%22interval%22:%22%22,%22intervalFactor%22:2,%22legendFormat%22:%22%7B%7Bdevice_name%7D%7D%20-%20%7B%7Bperformance_status%7D%7D%22,%22refId%22:%22A%22,%22editorMode%22:%22code%22,%22range%22:true,%22instant%22:true%7D%5D,%22range%22:%7B%22from%22:%22now-7d%22,%22to%22:%22now%22%7D,%22compact%22:false%7D%7D&orgId=1)

**Act on `Degraded`, but do not read `Healthy` as reassurance.** Per
[Google's documentation](https://docs.cloud.google.com/compute/docs/disks/disk-health) a
`Degraded` state is always caused inside Compute Engine, and explicitly *not* by workload traffic,
the machine type performance limit, or under-provisioned IOPS or throughput. In INC-14518 the
primary's boot disk turned `Severely Degraded` one minute before it hung, and
[PatroniPrimaryDiskDegraded](PatroniPrimaryDiskDegraded.md) now pages on it.

`Healthy` proves nothing. This status has also been observed staying `Healthy` for many hours after
a disk was already producing abnormal `await` on the primary, so keep working the workload when it
shows `Healthy`.

## Mitigate

Work down this list. Stop as soon as `await` recovers.

### 1. Raise the disk's provisioned IOPS or throughput — if you are actually at a limit

**Check the limits before doing anything else.** Raising provisioning only helps if the workload
has reached the disk's provisioned limit, or the VM's own IO limit. If you are nowhere near either,
more provisioning changes nothing, costs money, and wastes the time you needed for the real cause.

Compare current IO against the provisioned figures. These are the same ratios the existing
`disk_sustained_*` saturation points use, so a value near `1` means you are at the ceiling:

```promql
# read IOPS vs provisioned
rate(node_disk_reads_completed_total{env="gprd", fqdn="<primary>", device="<data-device>"}[5m])
  / node_disk_max_read_iops{env="gprd", fqdn="<primary>", device="<data-device>"}

# write IOPS vs provisioned
rate(node_disk_writes_completed_total{env="gprd", fqdn="<primary>", device="<data-device>"}[5m])
  / node_disk_max_write_iops{env="gprd", fqdn="<primary>", device="<data-device>"}

# read throughput vs provisioned
rate(node_disk_read_bytes_total{env="gprd", fqdn="<primary>", device="<data-device>"}[5m])
  / node_disk_max_read_bytes_seconds{env="gprd", fqdn="<primary>", device="<data-device>"}

# write throughput vs provisioned
rate(node_disk_written_bytes_total{env="gprd", fqdn="<primary>", device="<data-device>"}[5m])
  / node_disk_max_write_bytes_seconds{env="gprd", fqdn="<primary>", device="<data-device>"}
```

The same four ratios are graphed on the saturation dashboards:
[read IOPS](https://dashboards.gitlab.net/d/alerts-sat_disk_sus_read_iops),
[write IOPS](https://dashboards.gitlab.net/d/alerts-sat_disk_sus_write_iops),
[read throughput](https://dashboards.gitlab.net/d/alerts-sat_disk_sus_read_throughput),
[write throughput](https://dashboards.gitlab.net/d/alerts-sat_disk_sus_write_throughput).

Then decide:

- **Any ratio at or near 1** → the provisioned limit is the constraint. Raise it, as below. This is
  the preferred remedy: it does not touch the workload — nothing cancelled, paused or failed over —
  and it is reversible once the pressure is gone.
- **All ratios well below 1** → provisioning is not the constraint. Do not raise it. Either you are
  hitting the **VM's** IO limit, which is set by the machine type and caps aggregate IO no matter
  what the disk is provisioned for, or the disk is genuinely degraded, or a single workload is the
  cause. Continue from step 2.

If the VM limit is the ceiling, raising disk provisioning achieves nothing — that needs a machine
type change, which is not an in-incident action.

The provisioned figures for each cluster's data disk live in terraform, per environment:
[config-mgmt `environments/database-gprd`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/database-gprd).
Open an MR against the file for the affected cluster, raise the provisioned IOPS or throughput, and
get it applied.

Lower it again in a follow-up MR once the workload settles, so we do not carry the cost
permanently.

### 2. Stop the query driving it

If one query or backfill dominates, cancel it. Try cancel before terminate:

```sql
SELECT pg_cancel_backend(<pid>);
SELECT pg_terminate_backend(<pid>);
```

**Do not `kill -9` a PostgreSQL process.** It may force the instance through crash recovery,
dropping every connection rather than only the one you meant to stop — see
[handling unhealthy Patroni replica](../unhealthy_patroni_node_handling.md).

### 3. Throttle or reschedule the job

If a batch job, migration or backfill is responsible, pause it and reschedule outside peak hours.
Engage the owning team.

### 4. Leave autovacuum alone

If autovacuum on a large table is the driver, **let it finish**. Cancelling it only makes it
restart and repeat the same IO. If it recurs, tune `autovacuum_vacuum_cost_delay` for that table
afterwards.

### 5. Consider a switchover — last resort

**Only after the options above have been ruled out.** If step 1 showed you are at the provisioned
limit, raising it achieves the same relief without disrupting anything — do that instead.

**And do not switch over on a short spike.** A switchover costs a write-throughput hit and
invalidates connection pools. Storage contention often arrives as repeated bursts minutes or tens of minutes
apart, and failing over on each burst pays that cost every time and risks flapping between nodes —
which is worse than the contention.

Switch over when the saturation is **continuous** and tied to this node or zone. Before you do,
confirm a candidate replica is healthy, has low replication lag, and is in a different zone:

```
sudo gitlab-patronictl list
```

**Switchover, not failover, while the primary is still reachable.** A switchover waits for the
candidate to catch up, so nothing committed is lost. A failover does not wait, so any WAL the
candidate has not received is lost — only use it if the primary is stuck or unresponsive, and note
the candidate's lag at the time, because that is the upper bound on what went missing.

Full procedure, including the pre-checks:
[patroni-management.md — Failover/Switchover](../patroni-management.md#failoverswitchover).


## Alert behaviour

- Clears automatically once either condition drops below its threshold.
- Expected to be rare. Investigate a single firing even if it self-resolves — a burst that clears
  on its own can still be the first symptom of a disk or workload problem that will return.
- Silence only during an approved Change Request with known heavy IO, and keep the silence short
  and scoped.
- [Previous incidents for this alert](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=a%3APatroniPrimaryDiskIOSaturated)

## Escalation

- Cause not found and saturation persists → page `@dbre` in `#g_database_operations`.
- Users already affected → page `@dbre` and declare an incident in `#production`.
- After the event, re-check the GCP disk performance status. If it turned `Degraded` at any point,
  raise a GCP support case and record it on the incident. Its absence during the incident means
  nothing.

## Related links

- [Patroni service overview](../README.md)
- [Handling unhealthy Patroni replica](../unhealthy_patroni_node_handling.md)
- [Patroni management](../patroni-management.md)
- [PostgreSQL locking](../postgresql-locking.md)
- [Monitor disk health (GCP)](https://docs.cloud.google.com/compute/docs/disks/disk-health)
