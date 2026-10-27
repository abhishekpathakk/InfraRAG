# Project and group deletions failing on GitLab.com

This runbook covers diagnosing and mitigating a total or partial failure of
project and group deletions on GitLab.com, where deletions are enqueued but
never complete and the project or group stays in _Pending deletion_.

## Symptom

* Customers report projects or groups stuck in _Pending deletion_ well past
  their scheduled deletion date.
* `ProjectDestroyWorker` and/or `GroupDestroyWorker` error rates are elevated,
  or the `pending_delete` backlog age is growing.

## 1. Confirm the symptom

When namespace deletions are run via the `GroupDestroyWorker` or`ProjectDestroyWorker`,
they cascade to the namespace's child projects/groups too. If a child deletion fails,
the deletion of the parent breaks too.

Look for rolled-back destroy jobs and statement timeouts in
[the Sidekiq logs](https://log.gprd.gitlab.net/goto/d7e4791e63d2a2b192514ac821c9f14f).
Filter on the worker classes and a failure signature:

```
json.class: ("ProjectDestroyWorker" OR "GroupDestroyWorker")
  AND json.job_status: "fail"
```

To see the underlying database error, look at the Rails/PostgreSQL logs for a
statement timeout on a `DELETE` against a table referenced by `projects`, e.g.:

```
json.exception.class: ("PG::QueryCanceled" OR "ActiveRecord::StatementTimeout")
  AND json.sql: "DELETE FROM ONLY"
```

In [an earlier incident](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22727), the concrete error was
`PG::QueryCanceled: ERROR: canceling statement due to statement timeout` on
`DELETE FROM ONLY "public"."deployments" WHERE $1 = "project_id_convert_to_bigint"`.

### Rollback vs. a normally queued deletion

* A **normal queued deletion** has a `ProjectDestroyWorker`/`GroupDestroyWorker`
  job with `job_status: done` and the project/group disappears shortly after.
  A short spell in _Pending deletion_ is expected — deletions are asynchronous.
* A **rollback** is the failure case: the job runs, hits a statement timeout,
  the transaction rolls back, the job is marked `fail` (and retried), and the
  project returns to _Pending deletion_. The tell is repeated `fail` entries for
  the same project/group id alongside a `DELETE` statement timeout — the record
  never leaves the pending state no matter how long you wait.

## 2. Find the blocker

### Check the logs

Look at the logs from the Rails app, to see if a pattern emerges, that could point to the cause.

Ping the Entities team for a fix.

### Check if the blocker is a foreign key or referential integrity trigger

A potential cause is a foreign key or referential integrity trigger on `projects`
(or a table it cascades to) that fires on delete and is slow enough to time out.
The concerning case is a foreign key with `ON DELETE CASCADE` **whose referencing
column has no index** — every parent delete then triggers a sequential scan of
the child table.

Inspect the foreign keys referencing `projects` from a
[database console](../patroni/pg-ha.md) (or the read-only replica):

```sql
-- Foreign keys that reference projects, with their ON DELETE action.
SELECT conname,
       conrelid::regclass AS referencing_table,
       confrelid::regclass AS referenced_table,
       confdeltype,             -- 'c' = CASCADE, 'a' = NO ACTION, 'r' = RESTRICT
       pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE confrelid = 'projects'::regclass
  AND contype = 'f'
ORDER BY conname;
```

For each `ON DELETE CASCADE` foreign key, check whether the **referencing
column** on the child table is indexed. An FK whose referencing column has no
index is the culprit:

```sql
-- Does deployments.project_id_convert_to_bigint have an index? (worked example)
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'deployments'
  AND indexdef ILIKE '%project_id_convert_to_bigint%';
-- No rows -> unindexed -> every projects delete sequentially scans deployments.
```

Also check for referential integrity **triggers** on `projects` that fire on
delete:

```sql
SELECT tgname, pg_get_triggerdef(oid)
FROM pg_trigger
WHERE tgrelid = 'projects'::regclass
  AND NOT tgisinternal;
```

### Worked example: `fk_b9a3851b82_tmp`

The `deployments` bigint conversion left a temporary foreign key
`fk_b9a3851b82_tmp` (`deployments.project_id_convert_to_bigint` -> `projects.id`,
`ON DELETE CASCADE`). Migration `20260731085558`
(`DropTmpBigintIndexesAndFkForDeploymentsPhaseTwo`) was meant to drop it along
with the temporary indexes; the index drops landed but the FK removal did not
take effect. Because `project_id_convert_to_bigint` has no index, every project
delete fired the cascade as a sequential scan of `deployments`, timed out, and
rolled the destroy job back.

Related context: [#551602](https://gitlab.com/gitlab-org/gitlab/-/issues/551602)
(conversion tracking) and
[#609534](https://gitlab.com/gitlab-org/gitlab/-/work_items/609534) (the bug).

> **Verify the effect, not the migration status.** A migration reporting success
> does not prove the FK is gone — in INC-13111 the drop silently no-opped. Always
> confirm with the `pg_constraint` query above that the constraint is actually
> absent.

## 3. Mitigate: disable the destroy workers

Once you have confirmed deletions are rolling back, disable the destroy workers
to stop the failing jobs from retrying and burning database resources. This is
done with the standard Sidekiq worker feature flags (see
[Disabling Sidekiq workers](disabling-a-worker.md) for full detail):

```shell
# Defer (do not run) all ProjectDestroyWorker jobs
/chatops gitlab run feature set run_sidekiq_jobs_ProjectDestroyWorker false --ignore-feature-flag-consistency-check --ignore-production-check

# Defer (do not run) all GroupDestroyWorker jobs
/chatops gitlab run feature set run_sidekiq_jobs_GroupDestroyWorker false --ignore-feature-flag-consistency-check --ignore-production-check
```

### What this does and does not do

* **Does**: stops the destroy jobs from executing, so they stop rolling back and
  stop consuming database resources on doomed `DELETE`s.
* **Does**: preserve queued deletions. Jobs are *deferred*, not dropped — nothing
  is lost, so when the blocker is fixed the backlog drains without manual
  re-queuing. Do **not** drop these jobs.
* **Does not**: fix the deletions. Nothing completes while the workers are off;
  projects and groups stay in _Pending deletion_.
* **Does not**: stop users from *requesting* deletions. New requests keep
  enqueuing and add to the backlog.

### The backlog afterwards

The `pending_delete` backlog grows for as long as the workers are off. When the
blocker is removed and the workers are re-enabled, do so in a **staged rollout**
to avoid overloading the workers against a large backlog:

```shell
# Re-enable projects gradually, then fully; groups follow projects.
/chatops gitlab run feature set run_sidekiq_jobs_ProjectDestroyWorker 10 --actors --ignore-feature-flag-consistency-check
/chatops gitlab run feature delete run_sidekiq_jobs_ProjectDestroyWorker --ignore-feature-flag-consistency-check
/chatops gitlab run feature delete run_sidekiq_jobs_GroupDestroyWorker --ignore-feature-flag-consistency-check
```

Confirm you have not left a worker deferred forever:

```shell
/chatops gitlab run feature list --match run_sidekiq_jobs
```

## 4. Escalate

The mitigation buys time; removing the blocker usually needs a code or schema change.
A code change will be deployed via gitlab.com's usual deployments.

However, a schema change is a more complex problem since it cannot be a post-deployment migration and needs to be run under production load.

In this case, here are some points to note from our experience resolving incident INC-13111:

* **A post-deployment migration that cannot acquire its locks is a "schedule a
  maintenance window" problem, not a "retry with a longer timeout" problem.**
  Acquiring `ACCESS EXCLUSIVE` on a table as active as `projects` (or
  `deployments`) under weekday `.com` load does not fit in a PDM's ~10 minute
  budget. After the second consecutive lock-acquisition failure on a
  `gitlab_main` table, stop retrying and escalate to a change request.
* **Pull in Production Engineering / Release Management** to run the DDL as a
  [change request](https://gitlab.com/gitlab-com/gl-infra/production/-/issues)
  with SRE support. The DDL itself is fast (the INC-13111 `DROP CONSTRAINT` was
  ~3.9 ms); the cost is lock acquisition, which SRE can shepherd in a low-traffic
  window.
* **Check for a wraparound-prevention vacuum before booking the window.** In
  INC-13111 an autovacuum on `deployments` held a `ShareUpdateExclusiveLock`
  that blocked the `ACCESS EXCLUSIVE` locks twice, and it cannot be stopped (it
  restarts automatically). Read `pg_stat_activity` / `PostgresAutovacuumActivity`
  for the target tables *before* scheduling, not at execution time.
* **A post-deployment migration that no-opped may need re-running.** A guard that
  returns early (e.g. `WraparoundAutovacuum#can_execute_on?` returning `false`)
  is still recorded in `schema_migrations` as a success and will never run again.
  If the intended effect never took place, the migration has to be re-authored
  under a new name and re-run — verify the effect with the `pg_constraint` query,
  not the migration status.

## Related

* [Disabling Sidekiq workers](disabling-a-worker.md)
* [INC-13111 incident review](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22727)
* [#609534 — project/group deletions failing (bug)](https://gitlab.com/gitlab-org/gitlab/-/work_items/609534)
