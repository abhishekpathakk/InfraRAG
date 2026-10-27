# PatroniDelayedReplicaNoData

## Overview

No node of a delayed DR replica type has reported `pg_replication_lag` for 30 minutes. Until one
does, there is no delayed copy of that cluster, and
[PatroniDelayedReplicaLagOutOfBand](PatroniDelayedReplicaLagOutOfBand.md) can't fire for it.

The series disappears when:

- the VM is stopped,
- Postgres is down, for example when it stops with
  `new timeline N forked off current database system timeline N-1` after a failover, or
- postgres_exporter is down.

For example, after the
[INC-14518](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23026) failover the
main delayed replica (`postgres-delayed`) reported no lag at all:
`postgres-main-dr-delayed-v17-01` had stopped on timeline 2, and the series only came back once
its replacement, `postgres-main-dr-delayed-c4-v17`, was built.

## First steps

1. Find the cluster's delayed nodes and whether they're running:

   ```sh
   gcloud compute instances list --project gitlab-production --filter="labels.type=<type>"
   ```

2. On a running node, check Postgres and its exporter:

   ```sh
   sudo sv status postgres_exporter
   sudo gitlab-psql -Atc "select pg_is_in_recovery(), now() - pg_last_xact_replay_timestamp()"
   ```

3. If Postgres won't start, look at the end of the Postgres log. A timeline fork means the replica
   needs a rebuild, as described in Step 5 of
   [Primary unresponsive or no Leader](../primary-unresponsive-assess-before-failover.md#step-5-after-recovery).
4. If the node is being replaced on purpose, silence the alert for that `type` until the replacement
   reports, and link the change issue.

## Alert behaviour

- One alert per type, so a cluster with two delayed nodes fires only when neither reports.
- `for: 30m`: a restart or short VM maintenance rides through it.
- `s3`: Slack only, no page.

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-delayed-replica-alerts.libsonnet)
- [Link to edit this playbook](PatroniDelayedReplicaNoData.md)
- [Patroni management](../patroni-management.md)
