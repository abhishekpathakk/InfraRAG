# Adding a Patroni node that catches up from the WAL archive (`nostream`)

## Overview

Use this runbook when you add a node to an existing Patroni cluster and that node
will spend a long time replaying WAL from the wal-g archive before it can stream
from the leader. Typical cases:

- a new backup / LVM node whose data volume is restored with `wal-g backup-fetch`
  (many hours for the main and ci clusters)
- a replacement replica seeded from an old disk snapshot that has a lot of WAL to
  replay before it is current

For a plain read replica seeded from a fresh snapshot, [Scale Up Patroni](scale-up-patroni.md)
is enough. DR archive/delayed replicas are their own Patroni scope and do not create
slots on the production leader, so this runbook does not apply to them
(see [build_cluster_from_snapshot.md](build_cluster_from_snapshot.md)).

## Why

By default Patroni creates a physical replication slot on the leader for every
member as soon as the member registers in DCS. While the new node is replaying
from the archive it never connects to that slot, so the slot is inactive and the
leader keeps every WAL segment for it. During
[INC-12794](https://app.incident.io/gitlab/incidents/12794) the slot for
`patroni-main-v17-102` retained about 4 TB of WAL during a 17 h `backup-fetch`
and pushed the gprd main leader's disk towards capacity.

The `<env>-base-db-patroni-nostream` overlay role fixes this by setting the
Patroni `nostream` tag on the node from its very first chef run. Patroni skips
`nostream` members when it reconciles slots, so no slot exists on the leader
until the node is caught up and the role is removed.
The behaviour was validated end to end on `patroni-pmtest-v17` (db-benchmarking);
evidence is on [production-engineering#29507](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29507#note_3846706041).

## What the role does

`roles/<env>-base-db-patroni-nostream.json` in chef-repo (exists for
`db-benchmarking`, `gstg` and `gprd`) sets three Patroni tags:

| Tag | Effect while the role is applied |
| --- | -------------------------------- |
| `nostream: true` | The leader creates no replication slot for this member. The node recovers through `restore_command` (`wal-g wal-fetch`) instead of streaming. |
| `nofailover: true` | The node cannot be promoted while it is behind. |
| `noloadbalance: true` | The Patroni `/replica` endpoint answers 503, so Consul keeps the node out of the read pool. |

The tags are reload-safe. Removing the role and running `chef-client` rewrites
`patroni.yml` and reloads Patroni (no restart). Patroni then creates the slot,
PostgreSQL switches from `restore_command` to streaming, and the `noloadbalance`
tag goes away with the role.

## Hard rules

1. **The role has to be in the run_list from the first chef run.** Chef starts
   Patroni on first boot. If the role is added afterwards with `knife`, Patroni
   comes up without the tag and the slot appears on the leader immediately. The
   role therefore goes into the node's `chef_run_list_extra` in the config-mgmt
   MR that creates the node, never as a follow-up.
2. **Never pause the cluster while a member is away.** A paused leader does not
   reconcile slots. During validation a slot on a paused leader kept growing after
   its member was stopped and was only dropped 12 s after `patronictl resume`.
   Check `Maintenance mode` before you start and before go-live.
3. **Keep `chef-client` disabled while Patroni is stopped on the node.** Chef's
   systemd reload starts an inactive `patroni` unit. With an empty data directory
   that means Patroni bootstraps the node with `pg_basebackup` from the leader.

## Pre-checks

Run on the **current leader** of the target cluster.

1. The cluster is not paused.

   ```sh
   sudo gitlab-patronictl list
   ```

   You should see the member table and **no** `Maintenance mode: on` line.

2. No slot already exists for the node you are about to add. Slot names are the
   node FQDN with `.` and `-` replaced by `_`, cut to 63 characters, for example
   `patroni_main_v17_103_db_gprd_c_gitlab_production_internal`.

   ```sh
   sudo gitlab-psql -c "SELECT slot_name, slot_type, active, wal_status, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained FROM pg_replication_slots ORDER BY 1;"
   ```

   You should see the existing members and Siphon slots only. If a stale slot for
   the new node is there (for example from an earlier attempt), drop it before
   continuing:

   ```sh
   sudo gitlab-psql -c "SELECT pg_drop_replication_slot('<slot_name>');"
   sudo gitlab-psql -c "CHECKPOINT;"
   ```

3. Confirm which PostgreSQL major the archive backups were taken with, so the
   role, `data_directory` and `bin_directory` on the new node match the backup and
   not the `vNN` in a role filename:

   ```sh
   sudo -u gitlab-psql /usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g backup-list --detail | tail -3
   ```

## Step 1: Terraform MR, add the node with the role attached

In config-mgmt, add the node to the cluster's `nodes` map in
`environments/database-<env>/patroni-<cluster>.tf` and put the `nostream` role in
its `chef_run_list_extra`. Overlay roles are comma separated inside the quoted
string.

Backup / LVM node (keeps the cluster's `-backup-replica` overlay as well):

```hcl
103 = {
  machine_type        = var.machine_types["patroni-c4-highmem-96"]
  chef_run_list_extra = "\"role[${var.environment}-base-db-patroni-main-v17-backup-replica],role[${var.environment}-base-db-patroni-nostream]\""
  additional_labels   = { shard = "backup" }
}
```

Plain replica that will replay a long backlog:

```hcl
12 = {
  chef_run_list_extra = "\"role[${var.environment}-base-db-patroni-nostream]\""
  zone                = "us-east1-b"
}
```

Merge and apply through Atlantis as part of the CR. The plan must show exactly one
instance added and nothing replaced.

## Step 2: After bootstrap, confirm the tags landed

Wait for the node to register in Chef and for the first chef run to finish
(`gcloud compute instances tail-serial-port-output <instance> --zone <zone> --port 1`
shows the chef run).

1. On your **workstation**, the run_list carries the role:

   ```sh
   knife node show <node-fqdn> -r
   ```

   You should see `role[<env>-base-db-patroni-nostream]` in the run_list.

2. On the **new node**, the tags are in the Patroni config:

   ```sh
   sudo grep -A5 '^tags:' /var/opt/gitlab/patroni/patroni.yml
   ```

   You should see `nostream: true`, `nofailover: true` and `noloadbalance: true`.

3. On the **leader**, still no slot for the node:

   ```sh
   sudo gitlab-psql -c "SELECT slot_name, active FROM pg_replication_slots WHERE slot_name LIKE 'patroni_%' ORDER BY 1;"
   ```

If the tags are missing, stop here and fix the run_list before Patroni runs
without them (see [Troubleshooting](#troubleshooting)).

## Step 3: Get the data directory in place

Which variant applies depends on how the node was provisioned.

### Variant A: data disk seeded from a snapshot

Patroni started on first boot, found a data directory and is replaying WAL from
the archive. Nothing to do here, continue with Step 4.

### Variant B: empty data volume (LVM backup nodes)

The data volume is empty, so the base backup has to be fetched by hand before
Patroni is allowed to run. Do all of this on the **new node**.

1. Stop chef and Patroni:

   ```sh
   sudo chef-client-disable "<CR or issue link>"
   sudo systemctl stop patroni
   sudo systemctl is-active patroni
   ```

   You should see `inactive`.

2. Make sure the data directory is empty. The path follows the PG major, for
   example `/var/opt/gitlab/postgresql/data17`.

   ```sh
   sudo -u gitlab-psql bash -c 'ls -A /var/opt/gitlab/postgresql/data17 | wc -l'
   ```

   You should see `0`. If Patroni already started a `pg_basebackup` and left files
   behind, clear them. Run the removal inside `bash -c` as `gitlab-psql`; a plain
   `sudo -u gitlab-psql rm -rf <dir>/*` expands the glob as your own user, which
   cannot read the directory, and silently removes nothing.

   ```sh
   sudo -u gitlab-psql bash -c 'rm -rf /var/opt/gitlab/postgresql/data17/*'
   sudo -u gitlab-psql bash -c 'ls -A /var/opt/gitlab/postgresql/data17 | wc -l'
   ```

3. Fetch the base backup. This takes hours (about 17 h for the 60 TiB main
   cluster), so run it in `tmux` and log the output.

   ```sh
   sudo -u gitlab-psql /usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g backup-list
   ```

   ```sh
   sudo -u gitlab-psql /usr/bin/envdir /etc/wal-g.d/env /opt/wal-g/bin/wal-g backup-fetch /var/opt/gitlab/postgresql/data17 LATEST 2>&1 | tee /tmp/wal-g-backup-fetch.log
   ```

   You should see `Backup extraction complete` (or the wal-g equivalent for the
   installed version) at the end of the log and a populated `PG_VERSION` file in
   the data directory.

4. Start Patroni and re-enable chef. The `nostream` tag is already in
   `patroni.yml`, so Patroni starts PostgreSQL in archive recovery and the leader
   creates no slot.

   ```sh
   sudo systemctl start patroni
   sudo chef-client-enable
   sudo gitlab-patronictl list
   ```

   You should see the new member with state `in archive recovery` (Patroni 3.x)
   and its tags in the `Tags` column.

## Step 4: Monitor the catch-up

Expect this to take from minutes (snapshot seeded) to many hours (main/ci backup
nodes). Silence the replication-lag alerts for the new node for the expected
window, see [database_alert_management.md](database_alert_management.md).

On the **new node**:

```sh
sudo gitlab-patronictl list
```

`Lag in MB` should be falling. The state stays `in archive recovery` the whole
time; that is expected with `nostream`.

```sh
sudo tail -n 20 /var/log/gitlab/postgresql/postgresql.csv | grep -E 'restored log file|started streaming'
```

You should see `restored log file "..." from archive` lines and **no**
`started streaming WAL` line yet.

On the **leader**, every hour or so:

```sh
sudo gitlab-psql -c "SELECT slot_name, active, wal_status, pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained FROM pg_replication_slots ORDER BY 1;"
sudo gitlab-psql -c "SELECT application_name, state FROM pg_stat_replication ORDER BY 1;"
```

The new node must appear in **neither** result. If a slot for it shows up, go to
[Troubleshooting](#troubleshooting).

## Step 5: Go-live

Gate: `Lag in MB` on the new node is in the low single-digit GB or less and the
leader is not paused (`sudo gitlab-patronictl list` shows no `Maintenance mode`
line). Going live with a large lag is safe for the leader but the node will hold
the slot open while it finishes catching up over streaming.

1. Note the Patroni PID so you can confirm the switch was a reload. On the
   **new node**:

   ```sh
   systemctl show patroni -p MainPID
   ```

2. Remove the role. On your **workstation**:

   ```sh
   knife node run_list remove <node-fqdn> "role[<env>-base-db-patroni-nostream]"
   knife node show <node-fqdn> -r
   ```

   You should no longer see the `nostream` role. Any other overlays
   (`-backup-replica`, `-nofailover`) stay.

3. Apply it. On the **new node**:

   ```sh
   sudo chef-client
   sudo grep -A5 '^tags:' /var/opt/gitlab/patroni/patroni.yml
   systemctl show patroni -p MainPID
   ```

   You should see `nostream` gone from the tags and the same `MainPID` as in
   step 1 (reload, not restart). For a backup node `nofailover` and
   `noloadbalance` remain because the `-backup-replica` overlay sets them.

4. Confirm streaming started. On the **new node**:

   ```sh
   sudo grep -E 'started streaming WAL' /var/log/gitlab/postgresql/postgresql.csv | tail -1
   sudo gitlab-patronictl list
   ```

   You should see one `started streaming WAL from primary at ...` line with a
   timestamp after the chef run, and the member state changing from
   `in archive recovery` to `streaming` with `Lag in MB` dropping to 0. During
   validation the switch happened within one Patroni loop (about 10 s) and the
   remaining lag cleared in about 2 minutes.

5. Confirm the slot. On the **leader**:

   ```sh
   sudo gitlab-psql -c "SELECT slot_name, active, wal_status FROM pg_replication_slots WHERE slot_name LIKE 'patroni_%' ORDER BY 1;"
   sudo gitlab-psql -c "SELECT application_name, state, sync_state FROM pg_stat_replication ORDER BY 1;"
   ```

   You should see the node's slot with `active = t` and `wal_status = reserved`,
   and the node in `pg_stat_replication` with `state = streaming`.

6. Confirm read-pool membership matches the intent. On the **new node**:

   ```sh
   curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8009/replica
   dig @127.0.0.1 -p 8600 <read-service>.service.consul. SRV
   ```

   For a plain replica you should see `200` and the node in the SRV answer. For a
   backup node you should see `503` and the node absent, because
   `-backup-replica` keeps `noloadbalance`. The read service name is in the base
   role's `consul.services` (for example `db-replica` for main,
   `ci-db-replica-v18` for ci).

## Step 6: Terraform clean-up MR

`chef_run_list_extra` is only read at bootstrap, so the node is already correct.
Remove `role[${var.environment}-base-db-patroni-nostream]` from that node's entry
in config-mgmt so Terraform matches the live run_list, the same way the
long-term maintenance procedure in [patroni-management.md](patroni-management.md#long-term-marking-a-replica-as-in-maintenance)
reverts its role. The Atlantis plan must show an in-place metadata update only;
if it shows a replace, stop and ask in `#g_database_operations`.

## Troubleshooting

### A slot for the node appeared on the leader while it was still recovering

The tags did not make it into `patroni.yml` before Patroni started (rule 1). Fix
the run_list with `knife node run_list add <node-fqdn> "role[<env>-base-db-patroni-nostream]"`
and run `sudo chef-client` on the node. Patroni reloads with `nostream` and the
leader drops the slot within one loop; during validation the drop took under 10 s.
If the node is going to be down for a long time and the slot is already large,
drop it by hand on the leader:

```sh
sudo gitlab-psql -c "SELECT pg_drop_replication_slot('<slot_name>');"
sudo gitlab-psql -c "CHECKPOINT;"
```

### No slot appeared after go-live

Patroni caches the slots it manages. If a slot for this member was dropped by hand
earlier while the leader's Patroni still had it in its cache, Patroni may not
recreate it. Create it on the leader; Patroni adopts it on the next loop:

```sh
sudo gitlab-psql -c "SELECT pg_create_physical_replication_slot('<slot_name>');"
```

### The cluster is paused

Resume it before doing anything else (`sudo gitlab-patronictl resume --wait <scope>`).
A paused leader does not create or drop member slots.

### `rm -rf` on the data directory removed nothing

The glob expanded as your user. Use `sudo -u gitlab-psql bash -c '...'` as shown
in Step 3.

## References

- Patroni tags: <https://patroni.readthedocs.io/en/latest/yaml_configuration.html#tags>
- Related runbooks: [Scale Up Patroni](scale-up-patroni.md),
  [Patroni management](patroni-management.md),
  [wal-g backups](postgresql-backups-wale-walg.md)
