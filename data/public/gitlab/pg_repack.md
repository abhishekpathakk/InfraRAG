# Pg_repack using gitlab-pgrepack

 Here the link to the video of the [runbook simulation](https://youtu.be/fXSEGypfHGs).

[gitlab-pgrepack](https://gitlab.com/gitlab-com/gl-infra/gitlab-pgrepack.git) is a helper tool for running pg_repack in GitLab environments. It is open source and works on top of the [pg_repack PostgreSQL](https://github.com/reorg/pg_repack) program.

## What is bloat?

Bloat can be seen as the "remains" of UPDATE and DELETE activity. It is important to distinguish the concepts of "dead tuples" and "bloat". When a row is updated or deleted, PostgreSQL creates new physical versions of rows – called "tuples". After transaction finishes, old tuples are marked as "dead". Accumulation of dead tuples (caused by a massive operation or temporary autovacuum's inability to clean up dead tuples promptly) leads to the situation, when autovacuum cleans many dead tuples at once, leaving significant "gaps" in physical layout (empty space in pages) – these gaps is what we call "bloat".

Both tables and indexes can be bloated. Two negative effects of the growing bloat are:

1. excessive disk space usage,
1. performance degradation (usually, high levels of index bloat are more dangerous for performance).

## Why pg_repack?

`VACUUM FULL` is a standard command that can be used to get rid of bloat. But, as opposed to regular `VACUUM` (executed either by autovacuum or manually), `VACUUM FULL` uses a long-lasting exclusive lock on the table (basically, recreating the table and its indexes), blocking all the queries to the table and impacting performance. `Pg_repack` uses an approach that requires short-lived locks, being obtained gracefully (with multiple attempts with `statement_timeout` gradually growing from `100ms` to `1000ms`), suitable for databases with high and concurrent activity.

## ⚠️ Mandatory pre-flight checklist for CI Postgres primaries

Running `pg_repack` (or any similarly disruptive maintenance, e.g. `VACUUM FULL`, `pg_squeeze`) against a **CI Postgres primary** (e.g. `patroni-ci`, shard `saas-linux-small-amd64`) requires completing this checklist first. This is a corrective action from two incidents (INC-13562, 2026-08-27; INC-13766, 2026-09-02) where a manually-run `pg_repack` against `ci_builds` held its initial copy transaction open long enough (~70 minutes) to pin the database-wide `xmin` horizon. This blocked autovacuum cluster-wide and degraded CI job pickup enough to breach SLO, even though the operation targeted only one table.

This mechanism is not specific to `pg_repack` — any tool that holds a long-running transaction while copying a large, busy table (`pg_squeeze`, certain `VACUUM FULL` patterns) can reproduce it. Treat this checklist as required for any such operation on a CI Postgres primary, not just `pg_repack` specifically.

### 1. Impacted tables and blast radius

- [ ] Identify every table targeted by this operation (at minimum, check for `ci_builds` and other high-write tables in the same database). See the [PostgreSQL Bloat Dashboard](https://dashboards.gitlab.net/d/postgresql-postgresql-bloat/postgresql3a-postgresql-bloat) and [postgres-checkup reports](https://console.postgres.ai/gitlab/reports) (`F004`/`F005`) to size current bloat per table.
- [ ] A pinned `xmin` blocks autovacuum database-wide, not just on the target table — see the anti-wraparound check in [Pre-run checks](#3-pre-run-checks) below before proceeding.

### 2. Disk capacity

- [ ] Confirm free disk headroom is at least **2x the target table's current size** (pg_repack duplicates the table during the copy).
- [ ] Confirm the host is not within 10% of GCP's 64 TB single-disk maximum. If it is, this operation cannot proceed until a non-disruptive space-reclamation plan is agreed (see [gitlab-com/gl-infra/production-engineering#29701](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29701) and [gitlab-org/gitlab#629095](https://gitlab.com/gitlab-org/gitlab/-/work_items/629095) for the current CI `ci_builds` case).

### 3. Pre-run checks

- [ ] Anti-wraparound risk: check `age(datfrozenxid)` for the database and for other high-write tables (not just the target) against `autovacuum_freeze_max_age`. Routine autovacuum naturally lags on busy CI tables under normal load and is not itself a red flag — but a table approaching `autovacuum_freeze_max_age` will force an anti-wraparound vacuum, which (unlike routine autovacuum) cannot be deferred or skipped, and a pinned `xmin` would block it. Reschedule if any table is within range; the low-traffic window in [Maintenance window](#4-maintenance-window) below is the practical way to keep margin here.
- [ ] No conflicting long-running transaction or vacuum already in progress (check `pg_stat_activity`).
- [ ] CI pending-jobs backlog: confirm the current backlog on the affected shard is at/near baseline before starting (a pre-existing backlog leaves no margin if the operation adds load).
- [ ] I/O and cache metrics: capture a baseline (disk IOPS/throughput/latency, buffer cache hit ratio) to compare against during the run.

### 4. Maintenance window

- [ ] Schedule during a low-traffic window (weekend preferred), outside Production Change Lock (PCL) periods.
- [ ] Open a change request (production issue) documenting the above, linked to this checklist.

### 5. Required approvers

- [ ] Minimum 2 on-call approvers before execution: 1 database engineer + 1 engineer from the team owning the affected service (e.g. CI infrastructure for `patroni-ci`). Both must sign off in the change issue.

### 6. Abort / rollback criteria

Define and monitor these live during the run; abort immediately if any are crossed:

- [ ] The repack's copy transaction has been open longer than **15–20 minutes** without completing.
- [ ] Any downstream SLI/SLO for the affected service (e.g. `ci_runner_jobs` apdex, job-pickup throughput) starts degrading.
- [ ] Disk I/O latency crosses the threshold in [Monitoring and best practices during repacking](#monitoring-and-best-practices-during-repacking) below (SSD latencies above 10ms).
- [ ] `pg_repack` is observed blocking regular database queries at all (see [Locking](#locking) below) — there is no tolerable lock-wait duration for this case; cancel immediately.

It is always safe to interrupt `pg_repack` with `SIGTERM` — see [Cleanup activity](#cleanup-activity).

When you abort, close the annotation and Slack thread from [step 7](#7-announce-the-operation-to-responders) with the outcome `aborted`.

### 7. Announce the operation to responders

On-call responders must be able to see that a long-transaction maintenance operation is running. In INC-13766 the repack started at 10:30 UTC, CI job pickup started degrading at 11:15 and the apdex alert fired at 11:31. Nothing on the dashboards responders opened showed the repack, so linking it to the degradation took discussion on the incident call.

Do this immediately before starting the copy, and again when it finishes or is aborted:

- [ ] **Grafana annotation.** Create a `db-maintenance` annotation with the commands below. It is tagged with the cluster, so it shows only on that cluster's overview dashboard (`patroni`, `patroni-ci`, `patroni-sec` or `patroni-registry`) for the matching environment. `patroni-ci` markers also show on the `ci-runners` dashboards. Open your cluster's overview, for example [`patroni-ci`](https://dashboards.gitlab.net/d/patroni-ci-main), and confirm the marker appears before you continue.
- [ ] **Slack.** Post in `#production` with the change request link, the target table(s), the expected duration and who is watching the [abort criteria](#6-abort--rollback-criteria). Reply in that thread when the operation finishes or is aborted. Add the same updates to the change request.

You need a Grafana token with annotation write access (see [Prerequisites](#prerequisites)). The setup block keeps it out of your shell history and out of the process list: `read -rs` neither echoes nor records it, and `curl` reads the `Authorization` header from a file that only you can read (`mktemp` creates it with mode `0600`). Never paste the token into the change request, Slack or a URL.

Setup. In a new shell, for example to close the annotation later, run this block again:

```bash
GRAFANA_ENV=gprd      # as shown in the dashboard's environment dropdown, e.g. gprd, gstg, pre
CLUSTER=patroni-ci    # patroni, patroni-ci, patroni-sec or patroni-registry
OPERATION=pg_repack   # or pg_squeeze, VACUUM FULL, ...
TARGET=gitlab_partitions_dynamic.ci_builds
CR_URL=https://gitlab.com/gitlab-com/gl-infra/production/-/issues/NNNNN

GRAFANA_AUTH_HEADER=$(mktemp)
read -rsp 'Grafana token: ' token && echo
printf 'Authorization: Bearer %s\n' "$token" >"$GRAFANA_AUTH_HEADER"
unset token
```

Start, immediately before the copy. This creates the annotation and keeps its id for the end marker:

```bash
ANNOTATION_ID=$(
  jq -n --arg env "$GRAFANA_ENV" --arg cluster "$CLUSTER" \
    --arg text "${OPERATION} started on ${CLUSTER}: ${TARGET} (${CR_URL})" \
    '{time: (now * 1000 | floor), tags: ["db-maintenance", $env, "cluster:\($cluster)"], text: $text}' |
    curl -sSf -X POST https://dashboards.gitlab.net/api/annotations \
      -H @"$GRAFANA_AUTH_HEADER" -H 'Content-Type: application/json' --data @- |
    jq -r '.id'
)
if [[ "${ANNOTATION_ID}" =~ ^[0-9]+$ ]]; then
  echo "Annotation id: ${ANNOTATION_ID}"   # record it in the change request
else
  echo "Annotation was not created: fix this before starting the copy" >&2
fi
```

End. Set `OUTCOME` to `finished` or `aborted`. This sets the annotation's end time without moving its start, so the dashboards show the whole run as a region, and it removes the header file once the annotation is closed. In a new shell, take `ANNOTATION_ID` from the change request.

```bash
OUTCOME=finished   # or aborted
if [[ ! "${ANNOTATION_ID}" =~ ^[0-9]+$ ]]; then
  echo "ANNOTATION_ID is not a valid id: take it from the change request" >&2
elif jq -n --arg text "${OPERATION} ${OUTCOME} on ${CLUSTER}: ${TARGET} (${CR_URL})" \
  '{timeEnd: (now * 1000 | floor), text: $text}' |
  curl -sSf -o /dev/null -X PATCH "https://dashboards.gitlab.net/api/annotations/${ANNOTATION_ID}" \
    -H @"$GRAFANA_AUTH_HEADER" -H 'Content-Type: application/json' --data @-; then
  echo "Annotation ${ANNOTATION_ID} closed as ${OUTCOME}"
  rm -f "$GRAFANA_AUTH_HEADER"
else
  echo "Annotation ${ANNOTATION_ID} was not closed: re-run this block, or set its end time in Grafana, so it doesn't stay open" >&2
fi
```

Don't enable `gitlab-pgrepack`'s own Grafana integration (the `grafana.auth_key` config setting). Its built-in annotation is tagged `pgrepack` (not shown on these dashboards), and when a repack ends it overwrites the annotation's start time instead of setting its end time. It also labels aborted runs as `done`.

## How to see estimated bloat for tables and indexes

- In monitoring: [PostgreSQL Bloat Dashboard](https://dashboards.gitlab.net/d/postgresql-postgresql-bloat/postgresql3a-postgresql-bloat)
- [postgres-checkup reports](https://console.postgres.ai/gitlab/reports) – see reports `F004 Autovacuum: Heap Bloat (Estimated)` and `F005 Autovacuum: Btree Index Bloat (Estimated)`. See [Checking PostgreSQL health with postgres-checkup](postgres-checkup.md) for more information.

## What to repack

Bloat cannot be seen in exact numbers without expensive reading of database files, but we can have light checks providing estimates (which may be off up to dozens of percent in some cases, however). Usually, we consider bloat level of 20-30% as "normal", 50-60% as "significant", 80-90% as "high", and >90% as "extremely high".

Generally, we should start considering repacking indexes when the estimated bloat exceeds 50%, and definitely need to repack when it is greater than 60%. For tables, it depends: if we know that soon more data will be inserted to the table, we can skip repacking tables with a high level of bloat (two reasons: repacking of tables is lock-heavy, and also high table bloat usually doesn't affect performance directly), and we definitely should consider repacking tables with estimated bloat 90% and higher.

Of course, the repacking of tiny objects (such as tables or indexes which size is a few MiB) may not make sense and can be safely skipped.

## Prerequisites

- A Grafana token with annotation write access on `dashboards.gitlab.net`. It is required on CI Postgres primaries for [step 7 of the pre-flight checklist](#7-announce-the-operation-to-responders), and recommended everywhere else. Tokens come from a Grafana service account with the `Editor` role, managed in [grafana-management](https://gitlab.com/gitlab-com/gl-infra/observability/grafana-management/-/blob/main/README.md#adding-a-service-account), in the same way as `runway-deploy-annotations`. Ask the account's owners for a token rather than creating a personal one.

## Setting up the tool

Install dependencies, postgresql-17-repack, libpq and Ruby 3.1.2 (using RVM) in the console node:

```bash
sudo apt install gnupg2
sudo apt install postgresql-17-repack
sudo apt install libpq-dev

gpg2 --recv-keys 409B6B1796C275462A1703113804BB82D39DC0E3 7D2BAF1CF37B13E2069D6956105BD0E739499BDB
\curl -sSL https://get.rvm.io | bash -s stable
source ~/.rvm/scripts/rvm
rvm install 3.1.2
```

Install gitlab-pgrepack tool in your `$HOME`:

```bash
cd $HOME

git clone https://gitlab.com/gitlab-com/gl-infra/gitlab-pgrepack.git
cd gitlab-pgrepack
rvm use 3.1.2
gem install bundler
bundle install
```

## Configure gitlab-pgrepack

The configuration file is located at `~/gitlab-pgrepack/config/gitlab-repack.yml`. Main parameters to check/modify are:

- `host`: must point to the cluster leader (warning: you must not connect via pgBouncer; we need to control `statement_timeout`, so always connect directly to Postgres)
- `ratio_threshold`: Estimation of "how much bloat" is needed to be considered a `gitlab-repack` target. Any number between 60 and 80 is reasonable.
- `real_size_threshold`: minimum size (in bytes) to be considered a `gitlab-repack` target. Using 10000000 (10 MB) seems reasonable.

For fresh installs, you can configure the tool with this command (modify vaues as appropiate):

```bash
cat > ~/gitlab-pgrepack/config/gitlab-repack.yml <<EOF
general:
  env: local
database:
  adapter: postgresql
  host: patroni-04-db-gstg.c.gitlab-staging-1.internal
  user: gitlab-superuser
  password: xxx
  database: gitlabhq_production
estimate:
  ratio_threshold: 80 # bloat ratio threshold in % (set to 0 for testing)
  real_size_threshold: 10000000 # real size of object in bytes (set to 0 for testing)
  objects_per_repack: 1
repack:
  command: PGPASSWORD=xxx pg_repack -h patroni-04-db-gstg.c.gitlab-staging-1.internal -p 5432 -U gitlab-superuser -d gitlabhq_production --no-kill-backend
EOF
```

## Get objects that need to be repacked

The below command outputs both tables and indexes that will require repacking:

```
~/gitlab-pgrepack/bin/gitlab-pgrepack estimate
```

Depending on the values of

- `ratio_threshold`, and
- `real_size_threshold`

in your `gitlab-repack` configuration file, the output may vary, but in general, it will output the list of commands you need to execute. You can save them in a safe place, while you analyze the right order/time to do so:

```bash
gerardoherzig@patroni-04-db-gstg.c.gitlab-staging-1.internal:~$ ~/gitlab-pgrepack/bin/gitlab-pgrepack estimate

I, [2020-06-23T21:07:10.079325 #7531]  INFO -- : SET statement_timeout=0
I, [2020-06-23T21:07:10.079882 #7531]  INFO -- : SET idle_in_transaction_session_timeout=0
Note: This is based on an estimation of database bloat.
Note: Executing full table repacking also removes index bloat.

TABLE bloat:
64.64 GiB of bloat (24.5 % ratio of total size)
Recommended repacking for table bloat:
gitlab-pgrepack repack --type=tables --objects=public.project_mirror_data
gitlab-pgrepack repack --type=tables --objects=public.remote_mirrors
gitlab-pgrepack repack --type=tables --objects=public.ci_build_trace_section_names
gitlab-pgrepack repack --type=tables --objects=public.import_export_uploads
gitlab-pgrepack repack --type=tables --objects=public.geo_event_log
gitlab-pgrepack repack --type=tables --objects=public.ci_triggers
gitlab-pgrepack repack --type=tables --objects=public.pages_domains
gitlab-pgrepack repack --type=tables --objects=public.geo_repository_updated_events
gitlab-pgrepack repack --type=tables --objects=public.suggestions
gitlab-pgrepack repack --type=tables --objects=public.geo_node_statuses
Expected cleanup of 311.34 MiB of bloat.

INDEX bloat:
44.90 GiB of bloat (31.2 % ratio of total size)
Recommended repacking for index bloat:
gitlab-pgrepack repack --type=btrees --objects=public.index_user_highest_roles_on_user_id_and_highest_access_level
gitlab-pgrepack repack --type=btrees --objects=public.user_highest_roles_pkey
gitlab-pgrepack repack --type=btrees --objects=public.index_geo_reset_checksum_events_on_project_id
gitlab-pgrepack repack --type=btrees --objects=public.index_geo_event_log_on_container_repository_updated_event_id
gitlab-pgrepack repack --type=btrees --objects=public.geo_event_log_pkey
gitlab-pgrepack repack --type=btrees --objects=public.geo_reset_checksum_events_pkey
gitlab-pgrepack repack --type=btrees --objects=public.index_geo_event_log_on_reset_checksum_event_id
gitlab-pgrepack repack --type=btrees --objects=public.index_merge_request_diffs_on_merge_request_id_and_id_partial
gitlab-pgrepack repack --type=btrees --objects=public.index_namespaces_on_runners_token
gitlab-pgrepack repack --type=btrees --objects=public.index_namespaces_on_runners_token_encrypted
gitlab-pgrepack repack --type=btrees --objects=public.users_reset_password_token_key
gitlab-pgrepack repack --type=btrees --objects=public.index_users_on_group_view
gitlab-pgrepack repack --type=btrees --objects=public.index_users_on_accepted_term_id
```

## Script

- Open a `tmux` session before running this script.

```bash
### pg_repack can generate lots of WAL.
### Also, giving pg_repack more memory can speed up the process considerably.

sudo gitlab-psql -c "ALTER SYSTEM SET max_wal_size TO '16GB'";
sudo gitlab-psql -c "ALTER SYSTEM SET maintenance_work_mem TO '20GB'";
sudo gitlab-psql -c "SELECT pg_reload_conf();"


### On CI Postgres primaries: create the Grafana annotation and post in #production
### first (pre-flight checklist step 7), and close both when this block finishes.

### REPACKING GOES HERE

## Example of an index
~/gitlab-pgrepack/bin/gitlab-pgrepack repack --type=btrees --objects=public.index_chat_names_on_user_id_and_service_id

## Example for a table
~/gitlab-pgrepack/bin/gitlab-pgrepack repack --type=tables --objects=public.geo_node_statuses


### Restore the previous settings
sudo gitlab-psql -c "ALTER SYSTEM RESET maintenance_work_mem";
sudo gitlab-psql -c "ALTER SYSTEM RESET max_wal_size";
sudo gitlab-psql -c "SELECT pg_reload_conf();"
```

## Monitoring and best practices during repacking

### General advice

- ⚠️ The main danger during repacking is **disk IO**. Repacking is very IO intensive; it reads and writes a lot. So do it during a low-activity period of time – preferably, during a weekend.
- Closely watch monitoring (see details below) and be ready to slow down the process, or postpone it.
- Repacking of tables is beneficial but might be difficult (locking issues, a lot of IO). Consider skipping tables for which repacking fails due to locking issues and "downgrade" the operation to repacking only indexes of such tables.

### Disk IO

This is a must-have to monitor – check disks activity (first of all, `sdb`, where PostgreSQL data directory is located) to watch read and write IOPS, throughput, and latency. Additionally, closely monitor the general system performance – first of all, database request latencies (SQL query duration).

We still need to collect more experience and write more practical pieces of advice are to be written in this area (How to throttle if needed? What are the "limits" when we should take actions if things go south?). General advice: understand the limits and be ready to react to the increased latencies (SSD disk latencies above 10ms are considered as too high leading to user-facing performance degradation). Possible ways to react:

- If needed, feel free to interrupt repacking. It is safe to interrup the process with SIGTERM signal, the tool has [cleanup logic](https://gitlab.com/gitlab-com/gl-infra/gitlab-pgrepack/-/blob/master/lib/gitlab_repack/repack.rb#L88).
- Consider switching to process only indexes (repacking of indexes is the most beneficial in terms of performance and, sometimes, disk space saved).
- Tools like `ionice` and `renice` *may* be helpful to mitigate the impact here, but in practice, they do not always improve the performance picture.
- Introduce pauses between operations, split to work to batches. Do not push everything ASAP – usually, it is better to postpone the operation rather than to put the performance down.

### Lags

Increased WAL generation rates may lead to the situation when replicas are lagging behind significantly. Monitor the lags and be ready to slow down or even postpone the operation, not to allow replicas to have too high lags (many GiBs and many seconds).

### Locking

Locking activity must be properly monitored. Refer to the [locking activity](postgresql-locking.md) runbook for hints.

Both things can happen: pg_repack being blocked or pg_repack being blocking.

The first can be OK in many cases (for example, `VACUUM` running in the "transaction wraparound prevention mode" blocks pg_repack and doesn't yield). You can just wait for `VACUUM` to finish or *not* use `--no-kill-backend` in your `gitlab-repack` configuration (with care).

Pg_repack should never block regular database activity. In the case of normal queries being blocked by pg_repack activity, gitlab-repack should be canceled immediately!

### Activity

Most of the activity of pg_repack is to build the temporary table that will, eventually, replace the original (meaning that 2x space is required – if we are processing  the table of 100 GiB, we need additional 100 GiB temporarily):

```
-[ RECORD 1 ]----+----------------------------------------------------------------------------
datid            | 241498
datname          | pgrepack_test
pid              | 24505
usesysid         | 10
usename          | postgres
application_name | pg_repack
client_addr      | 127.0.0.1
client_hostname  |
client_port      | 54102
backend_start    | 2020-06-16 11:24:34.604791-03
xact_start       | 2020-06-16 11:25:35.270385-03
query_start      | 2020-06-16 11:25:35.27519-03
state_change     | 2020-06-16 11:25:35.275191-03
wait_event_type  |
wait_event       |
state            | active
backend_xid      | 2481299
backend_xmin     | 2481299
query            | INSERT INTO repack.table_241537 SELECT id,"time",data FROM ONLY public.test
backend_type     | client backend
```

## Cleanup activity

Under some circumstances (e.g., if your session crushes), pg_repack may not have been shut down cleanly. Our wrapper, gitlab-pgrepack, has some auto-cleanup logic for such cases, but still, you may need to take some actions to clean up.

1. Check for trigger (called `repack_trigger`) on the tables you were working on:

```
pgrepack_test=# \d test
                                      Table "public.test"
 Column |            Type             | Collation | Nullable |             Default
--------+-----------------------------+-----------+----------+----------------------------------
 id     | integer                     |           | not null | nextval('test_id_seq'::regclass)
 time   | timestamp without time zone |           |          |
 data   | text                        |           |          |
Indexes:
    "test_pkey" PRIMARY KEY, btree (id)
Triggers firing always:
    repack_trigger AFTER INSERT OR DELETE OR UPDATE ON test FOR EACH ROW EXECUTE PROCEDURE repack.repack_trigger('INSERT INTO repack.log_241537(pk, row) VALUES( CASE WHEN $1 IS NULL THEN NULL ELSE (ROW($1.id)::repack.pk_241537) END, $2)')
```

If that is the case, you can drop that trigger manually with:

```sql
drop trigger repack_trigger ON test;
```

1. You might also need to clean up the temporary table that pg_repack creates manually. First check for existence:

```
pgrepack_test=# \dt repack.
           List of relations
 Schema |    Name    | Type  |  Owner
--------+------------+-------+----------
 repack | log_241537 | table | postgres
(1 row)
```

Then, it is safe to drop the `repack` schema completely and re-install the `pg_repack` extension (dropping the table implicitly):

```sql
drop schema repack cascade;
drop extension pg_repack;
create extension pg_repack;
```

1. In rare cases, an advisory lock may be left by an interrupted repacking session – see such locks using `select * from pg_locks where locktype = 'advisory';` and use `pg_advisory_unlock(..)` function to remove the stale locks.
