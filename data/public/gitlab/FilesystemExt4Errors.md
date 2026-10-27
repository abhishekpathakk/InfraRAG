# FilesystemExt4Errors

## Overview

The kernel has recorded ext4 filesystem errors on a Gitaly node. `ext4` keeps a
persistent error counter in the filesystem superblock and increments it when it
detects metadata corruption, a failed journal commit, or an I/O error it cannot
transparently retry. The counter survives remounts and reboots, so a non-zero
reading is a record of damage rather than a transient condition.

On a Gitaly node the affected mount usually holds git repository data, so
corruption can surface to users as failed clones, fetches or pushes against the
repositories on that node, and in the worst case as data loss. The node may also
have remounted read-only, which fails every write to it.

The alert is a **cause** alert: it reports a hardware or filesystem fault, not
degraded user-facing SLIs. It is expected to be rare — over the 30 days to
2026-09-11 it did not fire at all, and no node's counter increased.

The recipient is expected to identify the affected node and mount, decide
whether the node is still safe to serve traffic from, and drain it if it is not.
Do not treat a firing as noise: nothing increments this counter under normal
operation.

## Services

- [Service Overview](../README.md)
- Team that owns the service: [Tenant Scale:Gitaly
  Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)

## Metrics

The alert reads `filesystem_ext4_errors_total`, a node-exporter counter of the
ext4 superblock error count, labelled by `fqdn`, `device` and `mountpoint`. The
unit is a count of errors, not a rate.

```promql
increase(filesystem_ext4_errors_total{env="gprd", service="gitaly"}[5m]) > 0
```

- The threshold is **any increase**, held for 5 minutes. There is no tuned
  value to choose: the counter only moves when the kernel has recorded a real
  error, so any movement is the signal. The 5-minute `for` exists to survive a
  single bad scrape, not to filter benign activity.
- Under normal conditions every series reads a constant value — usually 0 — and
  `increase()` is 0. As of 2026-09-11 there were 492 series across 164 Gitaly
  nodes in `gprd`, and `max(increase(...[30d]))` was 0.
- A node that has been reimaged can start a new series at 0. A node that
  previously recorded errors keeps its non-zero total; the alert fires on the
  *increase*, so a historical non-zero value does not re-fire by itself.

## Alert Behavior

- Expected to be rare. `ALERTS{alertname="FilesystemExt4Errors"}` had no samples
  over the 30 days to 2026-09-11.
- Silence only after the affected node has been drained or replaced, and scope
  the silence to that `fqdn`. A blanket silence on the alertname hides genuine
  corruption on every other node.

## Severities

- Configured as **s3**, so it does not page. It reports damage to one node, not
  a service-wide outage.
- Impact is limited to the projects whose repositories live on the affected
  node, so it is a subset of customers — but for that subset the impact can be
  severe (failed git operations, and potentially unrecoverable data).
- Raise severity if the node has remounted read-only, if more than one node is
  affected at once, or if Gitaly error-rate or apdex SLIs for the shard are also
  degraded. A single node with a small counter bump and healthy SLIs stays s3.

## Verification

- The query that triggered the alert:
  [`increase(filesystem_ext4_errors_total{env="gprd", service="gitaly"}[5m])`](https://dashboards.gitlab.net/explore?left=%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22expr%22:%22increase(filesystem_ext4_errors_total%7Benv%3D%5C%22gprd%5C%22,%20service%3D%5C%22gitaly%5C%22%7D%5B5m%5D)%22%7D%5D%7D)
- [Gitaly Service Overview
  dashboard](https://dashboards.gitlab.net/d/gitaly-main/gitaly-overview?orgId=1)
- [Gitaly host detail
  dashboard](https://dashboards.gitlab.net/d/gitaly-host-detail/gitaly-host-detail?orgId=1)
- Take the affected node and mount from the `fqdn`, `device` and `mountpoint`
  labels on the firing series.
- On the node, the kernel's own record is authoritative and more detailed than
  the counter:

  ```shell
  dmesg -T | grep -i -E 'ext4|i/o error|remount'
  sudo dumpe2fs -h /dev/<device> | grep -i -E 'error|state|mount'
  mount | grep -w /var/opt/gitlab   # is it ro?
  ```

  `dumpe2fs -h` reports `FS Error count`, the first and most recent error, and
  the filesystem state. A state other than `clean` means the filesystem needs
  attention before the node serves traffic again.

## Troubleshooting

Cheapest first:

1. Confirm the mount is still read-write. A read-only remount is the case that
   needs immediate action, because every write to that node is already failing.
2. Read `dmesg` for the underlying cause. An I/O error points at the disk or the
   GCE persistent disk / local NVMe beneath it; a metadata error with no I/O
   error points at filesystem corruption.
3. Check whether the counter is still climbing, or recorded a single event and
   stopped. A one-off with a clean filesystem state and healthy SLIs is a
   different problem from a node actively accumulating errors.
4. Check the Gitaly SLIs for the affected shard, to establish whether users are
   being served errors from this node right now.
5. Check whether other nodes in the same zone or of the same machine type are
   affected, which would suggest an infrastructure-wide fault rather than one
   bad disk.

Do **not** run `fsck` on a mounted filesystem, and do not resize or repartition
the volume to "clear" the counter. The counter is a record; clearing it destroys
the evidence without fixing the cause.

## Possible Resolutions

- **Single transient I/O error, filesystem clean, SLIs healthy.** Record it and
  monitor. No action is a valid outcome here.
- **Counter still climbing, or filesystem not clean.** Drain the node and move
  its repositories off, then have the disk replaced. See
  [move-repositories](../move-repositories.md) and
  [new-storage](../new-storage.md).
- **Node remounted read-only.** Treat as an outage for the repositories on that
  node: drain it immediately rather than waiting for a repair.
- **Repository-level corruption reported by users on this node.** See
  [gitaly-repository-corruption](../gitaly-repository-corruption.md).

## Escalation

Gitaly has a Tier 2 rotation. Follow the [How to
Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)
guidance to page the team.

Several Slack channels are also available:

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)
- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)
- [#infrastructure_platforms](https://gitlab.enterprise.slack.com/archives/C02D1HQRTKQ)

## Definitions

- [Alert
  definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/filesystem-ext4-errors-alerts.libsonnet)
- [Update the template used to format this
  playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
