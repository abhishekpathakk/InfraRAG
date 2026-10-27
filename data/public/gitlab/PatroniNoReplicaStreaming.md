# PatroniNoReplicaStreaming

## Overview

The cluster has replicas, but none of them has had a streaming WAL receiver for 2 minutes. From this
point on, **every commit on the primary exists on the primary alone**, apart from WAL segments it has
already archived, and a failover would lose it.

## Common causes

- **The leader lock is gone.** Patroni on each replica removes `primary_conninfo` once the leader key
  disappears, so all the replicas detach at once. On Sep 24 this happened at 22:49:56 while the old
  primary kept committing ([INC-14518](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23026)).
  Usually fires together with [PatroniNoHealthyPrimary](PatroniNoHealthyPrimary.md).
- **The replicas can't reach the primary** on port 5432, or the primary isn't sending WAL. The
  receivers then sit in `waiting` rather than `streaming`.
- **Every replica is being rebuilt at the same time**, for example with concurrent `pg_rewind` after a
  failover. Bring them back one or two at a time.

## First steps

1. On any replica, check the WAL receiver:

   ```sql
   select status, sender_host, last_msg_receipt_time from pg_stat_wal_receiver;
   ```

   No row means the replica has detached. `waiting` means it can't get WAL from the primary.
2. Check whether there is a Leader: `sudo gitlab-patronictl list`.
3. Check whether the primary is still committing. From a replica, run this twice, 10 s apart:

   ```sh
   timeout 15 sudo gitlab-psql -h <primary-fqdn> -Atc "select now(), pg_current_wal_lsn()"
   ```

   If the LSN moves, the primary is writing data that no replica has. A stalled node can hang new
   connections, so `timeout` keeps the check from hanging too. **If it times out, assume the primary
   is still writing.**
4. If there is no Leader, or the primary is unresponsive, follow
   [Primary unresponsive or no Leader: recover it without losing data](../primary-unresponsive-assess-before-failover.md).
   **Don't fail over first.**

## Why this signal

The rule reads the replicas' own `postgres_exporter`, so it doesn't depend on the primary. A replica
with no WAL receiver has no `pg_stat_wal_receiver` row, so its `pg_stat_wal_receiver_status` series
disappears. `2` means `streaming`.

A missing series can also mean the receiver query itself is broken. So the rule also needs proof that
the query works:

- **A replica of another cluster in the same environment is streaming.** This is the normal case: on
  Sep 24 the other clusters kept streaming, so this alert would have fired at about 22:52.
- **Or a replica of this cluster is more than 30 s behind** (`pg_replication_lag`, from the separate
  `pg_replication` query). This covers every cluster losing its leader at once. It isn't the main
  signal, because the exporter reports 0 lag for a replica restarted with nothing replayed yet, and
  replicas replaying from the WAL archive stay only a few seconds behind.

If neither holds, nothing is streaming anywhere and no lag is growing. That means the query is broken
on every node, and the rule stays silent instead of paging every cluster.

## Alert behaviour

- `for: 2m`: replicas that reattach after a switchover normally clear it first.
- Doesn't fire while at least one replica is streaming, so a single replica out for maintenance
  won't trigger it.
- Only `shard="default"` replicas count, as in the other Patroni alerts. Backup nodes follow the same
  leader, so they detach with the others.
- Clears as soon as any replica streams again.
- Clearing doesn't mean it's safe: after a failover the replicas stream from the new primary, even if
  the old one is still committing. See
  [PatroniNoHealthyPrimary](PatroniNoHealthyPrimary.md#alert-behaviour).
- **Expected while you follow the [recovery runbook](../primary-unresponsive-assess-before-failover.md):**
  the replicas stay detached until the old primary is Leader again. Acknowledge it rather than
  silencing it.

## Escalation

Writes are unprotected until a replica streams again. Declare an incident, and escalate to the DBO
(Database Operations) on-call with `/incident escalate` in the incident channel
([manual escalation](../../incident-io/oncall.md#manual-escalation)).

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-leadership-alerts.libsonnet)
- [Link to edit this playbook](PatroniNoReplicaStreaming.md)
- [Patroni management](../patroni-management.md)
