# PatroniPrimaryDiskDegraded

## Overview

Compute Engine has reported one of the primary's disks as `Degraded` or `Severely Degraded` for 3
minutes. Per [Google's documentation](https://docs.cloud.google.com/compute/docs/disks/disk-health),
this state is caused inside Compute Engine. It is **not** caused by our workload, the machine
type's IO limit, or under-provisioned IOPS or throughput, so tuning queries or raising provisioning
won't fix it.

The `device_name` label says which disk it is:

| `device_name` | Disk | What to expect |
| --- | --- | --- |
| `<instance>` | Boot | Consul, Patroni and the exporters run from it and may freeze. Watch for [PatroniPrimaryDiskStalled](PatroniPrimaryDiskStalled.md). |
| `<instance>-data` | `/var/opt/gitlab`, the database | Slow commits and pgbouncer queueing. Watch for [PatroniPrimaryDiskIOSaturated](PatroniPrimaryDiskIOSaturated.md). |
| `<instance>-log` | `/var/log` | Usually little user impact. |

## First steps

1. Check whether the node still responds: `sudo gitlab-patronictl list` from any cluster member,
   and the primary's metrics on the [Patroni overview dashboard](https://dashboards.gitlab.net/d/patroni-main/patroni-overview).
2. If the primary is unreachable, or there's no Leader, follow
   [Primary unresponsive or no Leader: recover it without losing data](../primary-unresponsive-assess-before-failover.md).
   **Do not fail over** before it has shown that the old primary isn't writing.
3. If the primary is still healthy, plan a switchover off this node with the DBO on-call rather than
   waiting for the disk to fail. A switchover waits for the candidate to catch up, so nothing
   committed is lost ([Patroni management](../patroni-management.md#failoverswitchover)).
4. Open a GCP support case for the disk, quoting the instance, `device_name`, the status and when it
   started, and record the case on the incident. Check
   [Personal Service Health](https://console.cloud.google.com/servicehealth) for a matching event.

## Why this signal

On Sep 24 (INC-14518) the boot disk of `patroni-main-v17-01-db-gprd` turned `Severely Degraded` at
22:44, one minute before it stopped completing writes and five minutes before user impact. Its data
and log disks stayed `Healthy`. This doesn't make the status a reliable real-time signal: it has
also stayed `Healthy` for hours while a disk produced abnormal latency (see
[PatroniPrimaryDiskIOSaturated](PatroniPrimaryDiskIOSaturated.md#gcp-disk-performance-status)). Act
on it when it fires, but don't read `Healthy` as reassurance.

## Alert behaviour

- Compute Engine publishes the status up to 4 minutes after it samples it, so this fires 5 to 7
  minutes after Compute Engine detects the problem.
- `for: 3m`. Clears when the disk returns to `Healthy` or the node is demoted to replica.
- The primary is found from the last role its own postgres_exporter reported in the past 12 hours,
  so the alert survives that exporter dying with a hung boot disk. **It resolves on its own 12 hours
  after the exporter stopped reporting**, even if the disk is still degraded: re-run the query below
  before treating it as recovered.
- Primary only, because that's where a disk problem becomes an outage. A degraded replica disk is
  visible in the query below.
- Uses series the stackdriver-exporter already collects.

```promql
stackdriver_gce_instance_compute_googleapis_com_instance_disk_performance_status{
  env="gprd",
  device_name=~"patroni.*",
  performance_status=~"Degraded|Severely Degraded"
} > 0
```

## Escalation

- Primary unreachable or no Leader: declare an incident and escalate to the DBO (Database Operations)
  on-call with `/incident escalate` ([manual escalation](../../incident-io/oncall.md#manual-escalation)).
- Primary healthy: raise it with the DBO on-call in `#g_database_operations` to plan the switchover.

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-gcp-disk-alerts.libsonnet)
- [Link to edit this playbook](PatroniPrimaryDiskDegraded.md)
- [Corrective action: GCP-level disk metrics as a fallback signal](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23154)
- [Monitor disk health (GCP)](https://docs.cloud.google.com/compute/docs/disks/disk-health)
