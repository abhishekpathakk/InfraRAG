# PatroniPrimaryDiskStalled

## Overview

Compute Engine reports that the primary's **boot disk** has requests queued and has completed no
writes for 3 minutes. The device is hung, not idle: a Patroni node's boot disk is never quiet,
because journald, the exporters and Consul write to it constantly.

This is the INC-14518 failure
([incident review](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23026)). Consul,
Patroni, node_exporter and postgres_exporter all run from the boot disk, so they freeze together,
while Postgres can keep committing to its separate data disk. Expect:

- `PatroniScrapeFailures` and missing node metrics for the primary, which look like an exporter
  problem but aren't.
- [PatroniNoHealthyPrimary](PatroniNoHealthyPrimary.md) and
  [PatroniNoReplicaStreaming](PatroniNoReplicaStreaming.md) within minutes.
- SSH to the node hanging or timing out.

**Do not fail over** until the recovery runbook has shown that the old primary's WAL position isn't
moving. A failover discards every write that only the old primary has.

## First steps

1. Follow [Primary unresponsive or no Leader: recover it without losing data](../primary-unresponsive-assess-before-failover.md).
   Check 2 of its Step 2 (is the primary still writing?) works without SSH.
2. **Save the serial console now**, before anyone resets the VM. The kernel's hung-task messages for
   the stuck disk are often the only evidence, and the buffer rolls over:

   ```
   gcloud compute instances get-serial-port-output <instance> --project=gitlab-production --zone=<zone> > <instance>-serial.log
   grep -E 'blocked for more than|jbd2|EXT4-fs|I/O error' <instance>-serial.log
   ```

   `<instance>` is the `device_name` on the alert. The zone is on the instance in the GCP console,
   or from `gcloud compute instances list --filter="name=<instance>"`.
3. Check [Personal Service Health](https://console.cloud.google.com/servicehealth) and open a GCP
   support case for the disk. [PatroniPrimaryDiskDegraded](PatroniPrimaryDiskDegraded.md) often fires
   for the same disk; record both on the incident.

## Why this signal

Compute Engine measures the disk from the hypervisor, so these series keep arriving when everything
inside the guest has stopped. On Sep 24 the boot disk's write ops fell from about 120 a minute to 0
at 22:45 and never recovered, while its queue depth climbed to a constant 32: requests in flight,
none completing. The data and log disks kept writing normally.

```promql
# The two inputs, for the alerting node (replace <instance>)
stackdriver_gce_instance_compute_googleapis_com_instance_disk_average_io_queue_depth{env="gprd", device_name="<instance>"}
stackdriver_gce_instance_compute_googleapis_com_instance_disk_write_ops_count{env="gprd", device_name="<instance>"}
```

The primary is found from the last role its own postgres_exporter reported in the past 12 hours,
because that exporter dies with the disk.

## Alert behaviour

- **Slow by design.** Compute Engine publishes disk samples up to 4 minutes after it takes them, so
  this fires 5 to 7 minutes after the disk hangs. It's a fallback that names the cause, not a fast
  pager: the leadership alerts usually fire first.
- `for: 3m`, which is three consecutive one-minute GCP samples.
- Boot disk only. A data disk can legitimately go a minute without writes on a quiet cluster.
- Primary only. A hung replica boot disk shows up as `PatroniScrapeFailures` and replication lag
  for that node.
- Clears when the disk completes writes again, or once a switchover has demoted the node and it
  reports as a replica. It keeps firing after a failover while the old primary is still frozen,
  because its last reported role stays primary.
- **Resolves on its own 12 hours after the node's postgres_exporter stopped reporting**, even if the
  disk is still hung, because the alert can no longer tell that the node was the primary. A resolve at
  that point doesn't mean the disk recovered: check the queue depth and write ops queries above.
- Can't fire unless the stackdriver-exporter collects
  `compute.googleapis.com/instance/disk/average_io_queue_depth` and `write_ops_count`
  ([argocd/apps `services/stackdriver-exporter`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/stackdriver-exporter)).

## Escalation

This is an outage for the cluster. Declare an incident, and escalate to the DBO (Database Operations)
on-call with `/incident escalate` in the incident channel
([manual escalation](../../incident-io/oncall.md#manual-escalation)).

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-gcp-disk-alerts.libsonnet)
- [Link to edit this playbook](PatroniPrimaryDiskStalled.md)
- [Corrective action: GCP-level disk metrics as a fallback signal](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23154)
- [Monitor disk health (GCP)](https://docs.cloud.google.com/compute/docs/disks/disk-health)
