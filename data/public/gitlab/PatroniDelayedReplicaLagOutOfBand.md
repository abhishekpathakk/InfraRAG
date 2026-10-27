# PatroniDelayedReplicaLagOutOfBand

## Overview

A delayed DR replica has been outside its replay window for 30 minutes. Each delayed replica
replays WAL from the archive 8 hours late (`recovery_min_apply_delay = 8h`), so that after a logical
error, such as a bad migration or a mass delete, or after a split brain, there is a copy of the data
from before it. That copy only exists while the replica stays close to 8 hours behind.

| Lag | What it means |
| --- | --- |
| More than 10 h | Archive replay is stuck or falling behind. On Sep 24 the main delayed replica was about 44 hours behind ([INC-14518](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23026)), so it couldn't serve as a pre-fork copy. |
| Less than 7 h | The delay isn't being applied. A logical error would reach this replica before anyone could stop it. |

This isn't an outage, and nothing serves traffic from these nodes. It's a gap in recovery options,
so fix it within working hours.

The delayed replicas are standby clusters (types `postgres-delayed`, `patroni-ci-delayed`,
`patroni-sec-delayed`, `patroni-registry-delayed`), and they exist only in gprd.

## First steps

1. On the node in the alert, check replay:

   ```sql
   select now() - pg_last_xact_replay_timestamp() as lag,
          pg_is_wal_replay_paused() as paused,
          pg_last_wal_replay_lsn(),
          current_setting('recovery_min_apply_delay') as apply_delay;
   ```

2. **Paused on purpose?** During an incident, responders may pause replay to keep a pre-fork copy.
   Check the incident channel. If so, silence the alert for that `fqdn`, with the incident link, until
   the copy is no longer needed.
3. **More than 10 h behind and not paused:** look for `restore_command` failures in the Postgres log:

   ```sh
   sudo grep -a -E 'restore_command|wal-fetch|could not|FATAL|forked off' /var/log/gitlab/postgresql/postgresql.csv | tail -20
   ```

   - **`new timeline N forked off current database system timeline N-1`** means the replica followed
     the old timeline past a failover and needs a rebuild. See Step 5 of
     [Primary unresponsive or no Leader](../primary-unresponsive-assess-before-failover.md#step-5-after-recovery).
   - **wal-g errors** usually mean the WAL segments aren't in GCS yet, or the archive is broken. Check
     archiving on the cluster's primary.
   - A replica that was just rebuilt catches up from its base backup, so it fires until it's back
     inside the window.
4. **Less than 7 h behind:** compare `apply_delay` with the role (`recovery_min_apply_delay` in
   chef-repo `roles/gprd-base-db-patroni-*-delayed-*.json`). A cleared delay, for example from a manual
   `gitlab-patronictl edit-config`, needs putting back. Also check that the node hasn't been promoted:
   `select pg_is_in_recovery();` must be `t`.

## Alert behaviour

- `for: 30m`: a restart rides through it. Until the first commit is replayed, the exporter reports 0
  lag, because `GREATEST(0, NULL)` is 0.
- One alert per node (`fqdn`). If a delayed replica stops reporting entirely,
  [PatroniDelayedReplicaNoData](PatroniDelayedReplicaNoData.md) fires instead.
- `s3`: Slack only, no page.

## Escalation

If the delayed copy of a cluster will be unusable for more than a working day, raise it in
`#g_database_operations`.

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-delayed-replica-alerts.libsonnet)
- [Link to edit this playbook](PatroniDelayedReplicaLagOutOfBand.md)
- [Patroni management](../patroni-management.md)
