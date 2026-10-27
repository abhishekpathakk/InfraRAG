# Primary unresponsive or no Leader: recover it without losing data

**Use this when** the cluster has no `Leader`, or the primary is unreachable over SSH or its metrics
scrapes are failing. **Do not fail over first.**

A failover promotes a replica *without* the writes it never received. If the old primary's Postgres
is still running (for example, because only its OS disk or Patroni is stuck), the old primary is the
**most complete copy of the data**. This runbook recovers it **in place**, so no committed writes are lost.

> **This is not the normal failure case.** Normally Patroni and Consul handle a failed primary on
> their own: the primary renews its leader lock in Consul, and if the node, Postgres or Patroni goes
> down, the lock expires and Patroni promotes the most up-to-date replica. That's the right outcome
> when the old primary has stopped taking writes. This runbook is for the rare **half-dead** primary:
> its Patroni or Consul agent is stuck (for example, on a stalled OS disk), so it loses the leader
> lock, while its Postgres keeps running and committing writes that the replicas no longer receive.

Timebox: assessment ≤ 10 min.

## Before you start: is the watchdog active?

On any cluster member (the configuration is the same across the cluster):

```sh
ls -l /dev/watchdog; lsmod | grep softdog; sudo grep -A3 '^watchdog:' /var/opt/gitlab/patroni/patroni.yml
```

- **Not active** (no device, no module, no `watchdog:` block): follow this runbook. Nothing will
  fence the primary automatically. You have to.
- **Active:** the watchdog resets a primary that can no longer renew its leader lock, the Patroni TTL
  minus `safety_margin` after its last successful renewal (85 s with our current settings). That's
  just before the lock expires, while the replicas are usually still streaming, and a replica is then
  promoted automatically, before you can pause. In testing, only writes in flight at that moment were
  at risk. Go to [Step 5](#step-5-after-recovery), and keep the old primary's data disk.

## Step 1: Disable chef, then pause Patroni

First disable chef on the **healthy** members. Every chef run replaces the cluster's Patroni
configuration with the role's, which **removes the pause**. Exclude the stuck primary: `knife ssh`
would hang on it.

```sh
knife ssh 'roles:<cluster-role> AND NOT name:<primary-fqdn>' 'sudo chef-client-disable "INC-xxxx: paused for recovery"'
```

Then pause Patroni, from any healthy member. Pausing stops any replica from promoting. It never touches Postgres.

```sh
sudo gitlab-patronictl pause --wait
sudo gitlab-patronictl list | grep 'Maintenance mode'
```

> While paused there is **no automatic failover for any reason**, and the watchdog is inactive.
> Keep the pause as short as the assessment and recovery.

## Step 2: Assess (5 minutes)

Grafana queries use datasource `mimir-gitlab-gprd` and are written for the **main** cluster. For
other clusters, change `type` (`patroni-ci`, `patroni-sec`, `patroni-registry`) and, in the
PgBouncer query, `fqdn` to that cluster's PgBouncer hosts. For gstg, use `env="gstg"` and
`mimir-gitlab-gstg`.

Open the checks **together** ([all in Explore, main, last 6h](https://dashboards.gitlab.net/goto/ffzngg4vfe2o0b?orgId=1)),
or **one at a time** from the links in the table.

| # | Question | Check | How to read it |
| --- | --- | --- | --- |
| 0 | Has Consul lost the primary? | From any node: `consul members \| grep -E 'failed\|left'` and `consul kv get service/<scope>/leader` (`<scope>` is `scope:` in `patroni.yml`) | A failed primary plus a missing leader key means the lock has expired. That's why there's no Leader. It's usually the first signal. |
| 1 | Are the replicas receiving WAL? | [Grafana](https://dashboards.gitlab.net/goto/cfznhkhnxnw8wb?orgId=1): `count(pg_stat_wal_receiver_status{env="gprd", type="patroni"}) or vector(0)` vs `count(pg_replication_is_replica{env="gprd", type="patroni"} == 1)`. On a replica: `select status, sender_host, flushed_lsn, last_msg_receipt_time from pg_stat_wal_receiver;` | A detached replica's series disappears, so the first count drops below the second (or to 0). No row on a replica means it's detached. **This is when writes start existing only on the primary.** |
| 2 | Is the old primary still taking writes? | **Direct (preferred)**, from any replica, twice, 10 s apart: `sudo gitlab-psql -h <primary-fqdn> -Atc "select now(), pg_current_wal_lsn()"`. SSH to the primary isn't needed. **Fallback (incomplete):** [Grafana](https://dashboards.gitlab.net/goto/dfznhkl7ek83kb?orgId=1) `sum(rate(pgbouncer_stats_sql_transactions_pooled_total{env="gprd", fqdn=~"pgbouncer-0[0-9]-db-gprd.*", database="gitlabhq_production"}[2m]))` covers web and API only. | If the LSN moves, the primary is still writing. A low PgBouncer rate **doesn't** mean writes have stopped. **If you can't check, assume writes are continuing.** |
| 3 | How far behind are the replicas? | [Grafana](https://dashboards.gitlab.net/goto/ffznhkp6y5atcb?orgId=1): `max by (fqdn) (time() - pg_stat_wal_receiver_last_msg_receipt_time{env="gprd", type="patroni"})`. On each replica: `select pg_last_wal_receive_lsn(), pg_last_xact_replay_timestamp();` | How much exists only on the primary. Don't compute byte lag from Prometheus, because scrape timing makes it unreliable. |
| 4 | Is WAL reaching GCS? | [Grafana](https://dashboards.gitlab.net/goto/afznhkrwm6dj4c?orgId=1): `max by (fqdn) (pg_archiver_pending_wal_count{env="gprd", type="patroni"})` | Normally < 20; thousands means archiving is stuck, so **no replica can catch up from the archive**. |
| 5 | Is the primary's Patroni half-dead? | `curl -s --max-time 3 http://<primary>:8009/patroni \| jq '{state, role, lock_age_s: ((now\|floor) - .dcs_last_seen)}'`. The TTL is in `sudo gitlab-patronictl show-config \| grep ttl` | `role` `master`/`primary` with `lock_age_s` **below** the TTL: healthy. **Above** the TTL: **half-dead**. It's writing, has lost the lock, and nothing will fence it. A timeout means Patroni is dead or the node is frozen; rely on check 2. |

Record on the incident: when the replicas detached, whether the primary is still writing, and how far behind the replicas are.

## Step 3: Recover the old primary in place

1. **Save evidence if you can.** A reset loses what hasn't been written to disk:
   `gcloud compute instances get-serial-port-output <vm> --project=<project> --zone=<zone> > <vm>-serial.log`
2. **Reset the VM** with `gcloud compute instances reset <vm> --project=<project> --zone=<zone>` or
   from the GCP console, or restart Postgres if the node is still responsive. Committed transactions
   are safe in the WAL on the data disk. While paused, Patroni removes the leader lock once Postgres
   stops, but **no replica promotes**.

   If you restarted Postgres on a responsive node instead of resetting the VM, skip items 3 and 4:
   disable chef on the node (item 5), start Postgres by hand if it isn't already running (item 6),
   then continue from item 7.
3. **Wait for the node to come back (up to 10 minutes from the reset).** From your workstation,
   in separate terminals:

   ```sh
   # VM state: expect RUNNING
   gcloud compute instances describe <vm> --project=<project> --zone=<zone> --format='value(status)'
   # Boot progress, live (Ctrl-C to stop)
   gcloud compute instances tail-serial-port-output <vm> --project=<project> --zone=<zone>
   # Or scan for trouble: hung tasks, disk errors, emergency mode
   gcloud compute instances get-serial-port-output <vm> --project=<project> --zone=<zone> \
     | grep -iE 'blocked for more than|hung_task|I/O error|EXT4-fs (error|warning)|nvme.*(timeout|reset|error)|emergency mode'
   ```

   The serial output also carries syslog, so it's noisy, and it's a rolling buffer: after a reset,
   the new boot messages are at the end. Matches from before the reset may still be there, so check
   their timestamps.

   On any other cluster member, watch for the Consul agent to come back (expect `alive`).
   `<primary-short-name>` is the primary's `hostname -s`:

   ```sh
   watch -n 5 'consul members | grep <primary-short-name>'
   ```

   You can also watch the VM's disk I/O in the GCP console (VM → Observability → Disk).
   The node is back when SSH works: `ssh -o ConnectTimeout=10 <primary-fqdn> true`.

   - **Back within 10 minutes:** continue with the next step.
   - **Not back after 10 minutes:** go to [If the node doesn't come back](#step-4-if-the-node-doesnt-come-back).
4. **Check the node is healthy before starting Postgres** (on the node):

   ```sh
   uptime                                    # confirms it rebooted
   findmnt /var/opt/gitlab                   # data disk mounted, rw
   df -h /var/opt/gitlab
   sudo dmesg -T | grep -iE 'blocked for more than|I/O error|EXT4-fs (error|warning)|nvme.*(timeout|reset|error)'   # expect nothing
   sudo journalctl -b -p err --no-pager | tail -30
   systemctl is-active consul patroni
   sudo tail -5 /var/log/gitlab/patroni/patroni.log     # expect "PAUSE: postgres is not running"
   sudo -u gitlab-psql /usr/lib/postgresql/<ver>/bin/pg_ctl -D /var/opt/gitlab/postgresql/data<ver> status   # expect "no server running"
   ```

   Don't start Postgres if the data disk isn't mounted read-write, or if the kernel is still reporting
   hung tasks or disk errors. Go to [If the node doesn't come back](#step-4-if-the-node-doesnt-come-back) instead.
5. **Disable chef on the node before starting Postgres.** A chef run removes the pause, but only
   once this node shows `running`. So after the manual Postgres start, a chef run could un-pause the
   cluster before this node is Leader, and a replica would promote. Disable it, then check the chef
   runs since boot:

   ```sh
   sudo chef-client-disable "INC-xxxx: paused for recovery"
   sudo chef-client-is-enabled
   sudo journalctl -b -u chef-client --no-pager | grep -E 'Starting Cinc Client|Cinc Client finished' | tail -4
   ```

   No output means chef hasn't run since boot. If the last line is `Starting Cinc Client` with no
   `Cinc Client finished` after it, a run is in progress: wait for it to finish before starting Postgres.
6. **Start Postgres by hand.** Patroni doesn't start it while paused:

   ```sh
   sudo -u gitlab-psql /usr/lib/postgresql/<ver>/bin/pg_ctl -D /var/opt/gitlab/postgresql/data<ver> start
   ```

   `pg_ctl: another server might be running` is expected after a crash (a stale `postmaster.pid`).
   Watch crash recovery in the Postgres log. On a busy primary it can take several minutes:

   ```sh
   sudo tail -F /var/log/gitlab/postgresql/postgresql.csv | grep -a --line-buffered -E \
     'was interrupted|redo starts|redo in progress|redo done|ready to accept connections|FATAL|PANIC'
   ```

   Expect `database system was interrupted`, then `redo starts at …`, `redo in progress` every
   10 seconds on a long recovery, `redo done at …`, and finally `database system is ready to accept connections`.
7. **Confirm it's Leader on the same timeline:**

   ```sh
   grep -E "PAUSE: acquired session lock|PAUSE: no action" /var/log/gitlab/patroni/patroni.log | tail -3
   sudo gitlab-patronictl list      # the old primary = Leader, TL unchanged
   ```

   The replicas may start streaming from it again **before** you resume. That's expected.
8. **Only then resume**, and re-enable chef on all members:

   ```sh
   sudo gitlab-patronictl resume --wait
   knife ssh 'roles:<cluster-role>' 'sudo chef-client-enable'
   ```

> ⚠️ **Never resume while there is no Leader.** A replica will promote immediately, and every write
> that only the old primary has will be lost.

## Step 4: If the node doesn't come back

**Stay paused.** While the cluster is paused, no replica promotes and the data stays on the old
primary's disk. Nothing is lost while you troubleshoot.

- Bring in a second DBRE.
- Keep troubleshooting with the serial output and the checks in Step 3: hung tasks, disk errors,
  a boot stuck in emergency mode, the data disk not mounting.
- **Don't delete or detach the old primary's disks.**
- The second DBRE and the Incident Manager decide the next course of action.
- If the node comes back, return to [Step 3](#step-3-recover-the-old-primary-in-place) and continue from the node health check.

> **A failover is out of scope for this runbook.** It loses every write that only the old primary
> has, so it's a data-loss decision: don't make it alone. It needs a second DBRE to review and
> agree, with the Incident Manager informed.

## Step 5: After recovery

- **Delayed and archive replicas:** if the old primary's WAL past a fork reaches GCS, these replicas
  can follow the old timeline and then stop with
  `new timeline N forked off current database system timeline N-1 before current recovery point`.
  They then need a rebuild. Check their position (`select pg_last_wal_replay_lsn();`) against the fork
  LSN in the new timeline's `.history` file. Restarting a replica **before** it reaches the fork, once
  that `.history` file is in GCS, should make it follow the new timeline. That last step hasn't been
  tested yet, so confirm with a DBRE first. See also
  [Diverged timeline WAL in GCS](patroni-management.md#diverged-timeline-wal-segments-in-gcs-after-failover).
- Check that application traffic has recovered: error rates, and that the PgBouncer pools point at the primary.

## Notes and limitations

- **Assumes asynchronous replication.** With synchronous replication, a failover normally loses no
  confirmed writes, so recovering in place matters less. Update this runbook if that changes.
- **While paused, nothing is automatic.** No failover happens for *any* failure, and the watchdog is
  inactive. Keep the pause short, and have someone watching the cluster the whole time.
- **A VM reset is an unclean shutdown.** Postgres runs crash recovery on start, which can take minutes
  on a busy primary. Transactions that hadn't committed are rolled back, and client connections drop.
  Committed transactions are not affected.
- **Replicas catch up from the primary's replication slots.** If a slot is missing, or the WAL it
  needed was removed (`max_slot_wal_keep_size`), that replica needs a rebuild. The primary's data is
  unaffected.
- **Testing so far:** validated on a 2-node test cluster. Crash-recovery time and catch-up time at
  production scale haven't been measured yet.

## Validation

The recover-in-place procedure has been tested in the db-benchmarking environment: a VM reset of the
primary under write load, with replication cut. No rows were lost and there was no timeline change.
A game day in staging is planned.
