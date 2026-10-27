# Sidekiq Concurrency Limit

## Throttling/Circuit Breaker based on database usage

To protect the primary database against misbehaving/inefficient workers which can lead into incidents like
slowdown of jobs processing, web availability, etc, we have developed a circuit breaking mechanism
within Sidekiq itself.

When the database usage of a worker [violates an indicator](#database-usage-indicators), Sidekiq will throttle the worker by decreasing its concurrency limit
at an interval of every minute. In the worst case scenario, the worker's concurrency limit will be suppressed down to `1`.

Once the database usage has gone to a healthy level, the concurrency limit will automatically recover towards its default limit, but at a much slower rate than the throttling rate. The definition of the throttling/recovery rate is defined [here](https://gitlab.com/gitlab-org/gitlab/-/blob/ae8a9687d65573f2945863fda97f144381f2a782/lib/gitlab/sidekiq_middleware/throttling/strategy.rb#L9-12).

Observability around concurrency limit can be viewed at [sidekiq: Worker Concurrency Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq3a-worker-concurency-detail?from=now-24h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1).

> [!note]
> Since throttled jobs will spend its queueing time in a separate concurrency limit queue, the apdex of `sidekiq_queueing` SLI for the respective
> shard could be affected too if there are a lot of jobs for this worker being throttled.
> Only jobs for this worker class will however be affected, other jobs will start normally.

### Database usage indicators

There are 2 indicators on which the application will throttle a worker:

1. DB duration usage (primary DBs only)

   **Dashboard:**

   - [Main DB duration](https://log.gprd.gitlab.net/app/r/s/mvUdr)
   - [CI DB duration](https://log.gprd.gitlab.net/app/r/s/LcvLB)
   - [Sec DB duration](https://log.gprd.gitlab.net/app/r/s/bTMsh)

   > [!important]
   > Make sure to check all primary DBs usage, ie `json.db_main_duration_s`, `json.db_ci_duration_s` and `json.db_sec_duration_s`.
   > If any one of the DB duration limit is exceeded, throttling event will kick in.

   By default, the per-minute DB duration should not exceed a limit of
   20,000 DB seconds/minute on non-high urgency worker and
   100,000 DB seconds/minute on high-urgency workers ([source](https://gitlab.com/gitlab-org/gitlab/-/blob/ae8a9687d65573f2945863fda97f144381f2a782/lib/gitlab/sidekiq_limits.rb#L5-7)).

   The limits above can also be overwritten as described [below](#updating-db-duration-limits). To check the current limit:

   ```bash
   glsh application_settings get resource_usage_limits -e gprd
   ```

2. Number of non-idle DB connections

   **Dashboard**:

   - [pgbouncer connection saturation](https://dashboards.gitlab.net/d/pgbouncer-main/pgbouncer3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)
   - [pgbouncer-ci connection saturation](https://dashboards.gitlab.net/d/pgbouncer-ci-main/pgbouncer-ci3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)
   - [pgbouncer-sec connection saturation](https://dashboards.gitlab.net/d/pgbouncer-sec-main/pgbouncer-sec3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&viewPanel=panel-57)

   Sidekiq [periodically](https://gitlab.com/gitlab-org/gitlab/-/blob/d5a647efaf6930d99b5aac54d284a1780a57e6c1/lib/gitlab/metrics/samplers/stat_activity_sampler.rb#L7)
   samples non-idle DB connections from `pg_stat_activity` to determine which worker classes are consuming the most connections.

   The system determines the **predominant worker** (the worker consuming the most connections) by:

   1. [Summing the number of connections used by a worker over the last 4 samples of `pg_stat_activity`](https://gitlab.com/gitlab-org/gitlab/-/blob/d5a647efaf6930d99b5aac54d284a1780a57e6c1/lib/gitlab/sidekiq_middleware/throttling/decider.rb#L37-46) (approximately 4 minutes of data)
   2. The worker with the most aggregated connections is the "predominant worker"

### Throttling events

The table below illustrates what happens when each indicator is violated:

| Indicator 1 (DB duration) | Indicator 2 (DB connections) | Throttling Event                                                                                          |
| ------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| ❌                        | ✅                           | Soft Throttle                                                                                             |
| ❌                        | ❌                           | Hard Throttle                                                                                             |
| ✅                        | ❌                           | No throttling. Not throttled as some workers may momentarily hold many connections during normal workload |
| ✅                        | ✅                           | No throttling                                                                                             |

> [!note] Legends
>
> - ❌ - failed the indicator check
> - ✅ - passed the indicator check
> - Soft Throttle - worker's current limit decreased by 20% per minute
> - Hard Throttle - worker's current limit decreased by 50% per minute

### Updating DB duration limits

The DB duration usage described [above](#database-usage-indicators) can only be updated by calling the [application settings API](https://docs.gitlab.com/api/settings/#update-application-settings). It cannot currently be set using the admin web UI.

> [!important]
> The `resource_usage_limits` accepts a JSON validated by a [JSON schema](https://gitlab.com/gitlab-org/gitlab/-/blob/ae8a9687d65573f2945863fda97f144381f2a782/app/validators/json_schemas/resource_usage_limits.json#L1-1).

1. Prepare a JSON file. Here's an example to update a single worker `Chaos::DbSleepWorker` to have its own limit on the main DB:

   <details>
   <summary>Click to expand</summary>

   ```json
   ❯ cat rules.json
   {
     "rules": [
       {
         "name": "main_db_duration_limit_per_worker",
         "resource_key": "db_main_duration_s",
         "metadata": {
           "db_config_name": "main"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
          {
            "selector": "worker_name=Chaos::DbSleepWorker",
            "threshold": 5,
            "interval": 60
          },
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       },
       {
         "name": "ci_db_duration_limit_per_worker",
         "resource_key": "db_ci_duration_s",
         "metadata": {
           "db_config_name": "ci"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       },
       {
         "name": "sec_db_duration_limit_per_worker",
         "resource_key": "db_sec_duration_s",
         "metadata": {
           "db_config_name": "sec"
         },
         "scopes": [
           "worker_name"
         ],
         "rules": [
           {
             "selector": "urgency=high",
             "threshold": 100000,
             "interval": 60
           },
           {
             "selector": "*",
             "threshold": 20000,
             "interval": 60
           }
         ]
       }
     ]
   }
   ```

   </details>

   > [!note]
   > The `selector` field follows the same [worker matching query](https://docs.gitlab.com/administration/sidekiq/processing_specific_job_classes/#worker-matching-query)
   > which is used in sidekiq routing rules too.

   To prepare a file with the current configuration to edit, run:

   ```bash
   glsh application_settings get resource_usage_limits > rules.json
   ```

1. Run a helper script `glsh application_settings resource_usage_limits` to update the limits with an admin PAT.

   ```bash
   glsh application_settings set resource_usage_limits -f rules.json -e gprd
   ```

### Disabling the Throttling/Circuit Breaker feature entirely

To disable throttling globally for all workers:

```
/chatops gitlab run feature set sidekiq_throttling_middleware false
```

To disable throttling for a worker:

```
# replace Security::SecretDetection::GitlabTokenVerificationWorker with the worker you want to disable
/chatops gitlab run feature set `disable_sidekiq_throttling_middleware_Security::SecretDetection::GitlabTokenVerificationWorker` true
```

## SidekiqConcurrencyLimitQueueBacklogged Alert

This alert fires when a Sidekiq worker has accumulated too many jobs in the Concurrency Limit queue (>100,000 jobs for more than 1 hour).

The long backlog is usually caused by higher arrival rate of jobs compared to the rate of resumed jobs by `ConcurrencyLimit::ResumeWorker`.

- The arrival rate is equal to the worker deferment rate, which can be found in the [Worker deferment rate panel](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-693216408).
- The rate of resuming jobs can be found in [Kibana](https://log.gprd.gitlab.net/app/r/s/Aw54b).

If arrivals consistently exceed resumptions, consider increasing the worker limit when database capacity permits. Disabling the limit is described in Option 2 below.

These jobs are queued on the dedicated [`memorystore-redis-concurrency-limit`](../memorystore-redis-concurrency-limit/README.md) instance. A large backlog can saturate its memory. The instance runs `noeviction`, so at `maxmemory` new deferred jobs are rejected. Check its memory on the [overview dashboard](https://dashboards.gitlab.net/d/memorystore-redis-concurrency-limit-main/memorystore-redis-concurrency-limit-overview).

### Backlog that outlives its trigger (deferred-queue latch)

A backlog can keep growing after the condition that started it has cleared. This happened in
[INC-14968](https://app.incident.io/gitlab/incidents/14968) on 2026-10-08 and again on 2026-10-13, to
`Ci::ExecuteBuildHooksWorker`, `Ci::BuildTraceChunkFlushWorker` and `Ci::SyncReportsToReportApprovalRulesWorker`.
Root cause of the initial deferrals is tracked in [tenant-services/team#517](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/517).

#### Why it happens

[`Middleware#should_defer_perform?`](https://gitlab.com/gitlab-org/gitlab/-/blob/0adb3b882418edb82d13580d488b306af4bcf00a/lib/gitlab/sidekiq_middleware/concurrency_limit/middleware.rb#L63-69)
defers a job when the worker is over its limit **or** when its deferred queue is non-empty.
The second clause preserves ordering, but it means one deferral latches the worker: every new job goes to the queue until `ConcurrencyLimit::ResumeWorker` has emptied it.
Free execution slots do not clear the queue.

The drain is slower than the fill. [`QueueManager#num_jobs_to_resume`](https://gitlab.com/gitlab-org/gitlab/-/blob/8a6a9dbaca387bced29d401e3bf49cb3c4001bbb/lib/gitlab/sidekiq_middleware/concurrency_limit/queue_manager.rb#L235-242)
caps each resume pass at `limit - running - pending_resumed`, so resume throughput is bounded by free slots while the enqueue rate is not.
A short dip in capacity, such as a saturated Sidekiq pgbouncer pool, is enough to start the latch. The backlog then grows while incoming demand is falling.

#### How to recognise it

On the [Worker Concurrency Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1) with `worker` set to `All`:

- [`Worker deferment rate`](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-693216408) tracks the worker's normal enqueue rate while [`Worker concurrency`](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-3669824294) sits well below [`Max limit`](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-1043686054).
- `Concurrency limit queue sizes` is flat or rising 30 minutes after the [database usage indicators](#database-usage-indicators) and pgbouncer saturation have recovered.
- The `sidekiq_queueing` apdex on the worker's shard is degraded. On 2026-10-13 this was `catchall-b` for `Ci::ExecuteBuildHooksWorker` and `urgent-other` for `Ci::BuildTraceChunkFlushWorker`.

Do not wait for `SidekiqConcurrencyLimitQueueBacklogged`. It needs more than 100,000 jobs for an hour, and on 2026-10-13 it fired after mitigation had started.

#### What to do

1. Identify the exact worker from the [queue sizes panel](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-2282485207). Mitigation is per worker. On 2026-10-13 the first bypass targeted `Ci::BuildTraceChunkFlushWorker` while the backlog was on `Ci::ExecuteBuildHooksWorker`, which delayed recovery.
1. Confirm the trigger has cleared using the [database usage indicators](#database-usage-indicators). If the database is still saturated, the bypass below adds load to it; weigh that against the queueing impact.
1. Enable the per-worker bypass, as in [Option 2](#option-2-temporarily-disable-concurrency-limit):

   ```text
   /chatops gitlab run feature set `disable_sidekiq_concurrency_limit_middleware_Ci::ExecuteBuildHooksWorker` true --ignore-feature-flag-consistency-check
   ```

   Deferrals stop within a minute, so the queue stops growing. The bypass does not change the resume rate: `ResumeWorker` still resumes at most `limit - running - pending_resumed` jobs per pass, where `running` now includes jobs that bypassed the queue.
1. Post the worker name and the flag in the incident channel.
1. Watch `Worker deferment rate` drop to zero, then `Concurrency limit queue sizes` fall to zero. Watch memory on the [memorystore-redis-concurrency-limit overview](https://dashboards.gitlab.net/d/memorystore-redis-concurrency-limit-main/memorystore-redis-concurrency-limit-overview) while it drains.
1. Delete the flag once the queue is empty. A worker left bypassed has no concurrency protection.

   ```text
   /chatops gitlab run feature delete `disable_sidekiq_concurrency_limit_middleware_Ci::ExecuteBuildHooksWorker`
   ```

Reference drain time: on 2026-10-13 the bypass for `Ci::ExecuteBuildHooksWorker` was set at 14:16 UTC, deferrals stopped by 14:19, and 647,000 queued jobs were gone by 14:50.

#### Alternative not yet used in an incident

`concurrency_limit_eager_resume_processing` ([rollout issue](https://gitlab.com/gitlab-org/gitlab/-/issues/580062)) is an instance-wide `ops` flag, default off.
With it enabled, `ResumeWorker` loops resume passes for up to 5 minutes per run instead of one pass per run. It keeps the per-pass cap, so it drains faster only when free slots exist.
It has not been exercised during a production backlog. Prefer the per-worker bypass above unless the limit must stay in force while draining.

Related: [INC-14022](https://app.incident.io/gitlab/incidents/14022), [INC-13984](https://app.incident.io/gitlab/incidents/13984),
[production-engineering#30042](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/30042) (earlier paging for build-hook queueing).

### Option 1: Increase Worker Concurrency Limit

#### Temporary ChatOps override

This procedure requires deployment of the application API and ChatOps command tracked in
[production-engineering#29754](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29754).
Do not use these commands before both changes are deployed.

An override lets on-call raise or lower one worker's limit without disabling throttling globally, addressing incidents such as
[INC-14022](https://app.incident.io/gitlab/incidents/14022).

- Overrides take precedence over adaptive throttling and recovery for that worker.
- Limits must be positive integers; `0` (unlimited) is rejected.
- Workers without a limit can receive a temporary cap.
- Paused workers reject overrides; a subsequent pause takes precedence over an existing override.
- Overrides are inactive while the global concurrency-limit middleware is disabled.
- The read command also reports the worker-specific bypass flag. An override does not clear that flag.
- Lowering the limit does not stop running jobs. Running and deferred counts are approximate.
- Shard-derived class defaults cannot be calculated by the API; the read command reports them as unknown rather than unlimited.

##### How the TTL works

The TTL sets how long the override lasts: `1`–`86400` seconds, default `1800`.
While it is active, adaptive throttling skips the worker, so the limit stays fixed.

On expiry, the limit reverts to the stored adaptive limit, or the class default if that has also expired.
The adaptive limit expires 30 minutes after its last update, so longer overrides usually revert to the class default.
Running jobs are not interrupted.

The TTL means a forgotten override reverts without action from on-call.
Set it to the expected drain time. Run `set` again to extend it, or `reset` to end it early.

#### Procedure

1. Check database load using the [database usage indicators](#database-usage-indicators) before increasing the limit.

1. Inspect the worker's current limits and backlog:

   ```text
   /chatops gitlab run sidekiq concurrency-limit get Example::Worker --production
   ```

1. Set an absolute limit and a TTL covering the expected drain time, replacing the worker and example values:

   ```text
   /chatops gitlab run sidekiq concurrency-limit set Example::Worker 20 --ttl 1800 --production
   ```

1. Monitor throughput, deferred backlog and database saturation while the override is active.

1. Clear the override to restore normal limit handling:

   ```text
   /chatops gitlab run sidekiq concurrency-limit reset Example::Worker --production
   ```

Use `--staging` instead of `--production` for staging validation.

#### Permanent limit change

If the worker can safely handle more concurrent jobs:

1. Locate the worker definition in the codebase
2. Check current concurrency limit setting from the [dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=ProcessCommitWorker&orgId=1&viewPanel=panel-1043686054) or the worker class definition.
3. Create an MR to increase the limit to an appropriate value based on [concurrent jobs](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=ProcessCommitWorker&orgId=1&viewPanel=panel-3669824294)

If `concurrency_limit` attribute is not set in the worker class, consider overriding
[`max_concurrency_limit_percentage` attribute](https://gitlab.com/gitlab-org/gitlab/-/blob/fee2b14e9d2f47bbae7638cce1c04205703e6241/app/workers/flush_counter_increments_worker.rb#L27-27) to use higher percentage of max total threads in the Sidekiq shard. The default
percentage can be found [here](https://gitlab.com/gitlab-org/gitlab/-/blob/fee2b14e9d2f47bbae7638cce1c04205703e6241/app/workers/concerns/worker_attributes.rb#L44-49) (based on worker's urgency).

### Option 2: Temporarily Disable Concurrency Limit

Alternatively, `disable_sidekiq_concurrency_limit_middleware_#{worker_name}` feature flag can be enabled to help clear the backlogs instantly
without waiting for deployment as in Option 1.

1. Enable the feature flag:

```
/chatops gitlab run feature set `disable_sidekiq_concurrency_limit_middleware_WebHooks::LogExecutionWorker` true --ignore-feature-flag-consistency-check
```

2. Monitor the [concurrency limit queue size](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-2282485207) to confirm it's draining
3. If we decide to increase the concurrency limit, wait until the limit has been increased and disable the feature flag back:

```
/chatops gitlab run feature delete `disable_sidekiq_concurrency_limit_middleware_WebHooks::LogExecutionWorker`
```

When the concurrency limit middleware is disabled:

- New jobs will execute immediately, so the queue stops growing.
- The resume rate is unchanged: [`ResumeWorker`](https://gitlab.com/gitlab-org/gitlab/-/blob/fe174bdaabd0053087547903fbc2edaa63a8130e/app/workers/concurrency_limit/resume_worker.rb) still resumes at most `limit - running - pending_resumed` jobs per pass. The flag is read only by [`Middleware#disabled_for_worker?`](https://gitlab.com/gitlab-org/gitlab/-/blob/0adb3b882418edb82d13580d488b306af4bcf00a/lib/gitlab/sidekiq_middleware/concurrency_limit/middleware.rb#L129-136), not by `QueueManager#num_jobs_to_resume`.

### Post-Incident Tasks

1. Create an issue to properly address the root cause if Option 2 was used
2. Update monitoring thresholds if needed

## SidekiqWorkerThrottledByDBUsage Alert

This alert fires when a worker has been `HardThrottle`d continuously for more than 5 minutes.
It is an s3 symptom alert and does not page.

`HardThrottle` means the worker failed both [database usage indicators](#database-usage-indicators) in the same minute:
it exceeded its DB duration limit, and it was the predominant holder of non-idle DB connections.
Each minute in that state halves the worker's current concurrency limit, down to a floor of `1`. See [Throttling events](#throttling-events).

The alert is driven by `sidekiq_throttling_events_total{strategy="HardThrottle"}`, which the
[Throttling Events panel](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-1085115946)
plots per worker and strategy.

### What to check

1. Open the [Current limit panel](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-3955486249) for the worker. The gap between `Current limit` and `Max limit` is how far it has been throttled.
2. Check which indicator tripped. DB duration is in the Kibana links under [Database usage indicators](#database-usage-indicators); connection pressure is on the pgbouncer saturation panels linked there.
3. Check the [Concurrency limit queue sizes panel](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq-worker-concurrency-detail?from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1&viewPanel=panel-2282485207). A throttled worker defers jobs, so a sustained throttle turns into a [SidekiqConcurrencyLimitQueueBacklogged](#sidekiqconcurrencylimitqueuebacklogged-alert) alert.

### Resolution

Throttling is the system working as designed. The current limit recovers towards `Max limit` on its own once the worker's DB usage drops, at the recovery rate defined [here](https://gitlab.com/gitlab-org/gitlab/-/blob/ae8a9687d65573f2945863fda97f144381f2a782/lib/gitlab/sidekiq_middleware/throttling/strategy.rb#L9-12).

Intervene only when the throttle is causing user-facing impact or a backlog.

Do not raise the worker's DB duration limit as a fix. The limits are set per urgency class
([production#20787](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20787)).
A per-worker override skews DB usage across workers and is hard to rebalance later.

Find what increased the worker's DB usage:

1. Check whether a single user, project or namespace is driving the volume. In the [DB duration Kibana views](#database-usage-indicators), split by `json.meta.user`, `json.meta.project` or `json.meta.root_namespace` ([field reference](sidekiq-survival-guide-for-sres.md#logs)).
2. Check for fan-out. Split by `json.meta.caller_id` to see what is enqueuing the jobs.
3. Check for a recent change to the worker's code path. Compare the throttle start time against [recent deployments](https://dashboards.gitlab.net/d/general-deployment-home) and the worker's recent MRs.
4. Check for an unoptimised query. Use the [Marginalia sampler dashboard](sidekiq-survival-guide-for-sres.md#marginalia-sampler-dashboard) filtered to the worker's endpoint.

Then:

- Open an issue against the worker's owning group with the findings.
- If the throttle is causing a backlog, follow [SidekiqConcurrencyLimitQueueBacklogged](#sidekiqconcurrencylimitqueuebacklogged-alert).
- Disabling throttling for the worker ([Disabling the Throttling/Circuit Breaker feature entirely](#disabling-the-throttlingcircuit-breaker-feature-entirely)) is a last resort. Open a tracking issue to re-enable it.

## Useful Dashboards

- [sidekiq: Worker Concurrency Detail](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq3a-worker-concurency-detail?from=now-24h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&orgId=1)
- [memorystore-redis-concurrency-limit: Overview](https://dashboards.gitlab.net/d/memorystore-redis-concurrency-limit-main/memorystore-redis-concurrency-limit-overview?orgId=1&from=now-6h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd)
- [Sidekiq: Overview](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview)

> [!note] Blank dashboard
> If every panel on the Worker Concurrency Detail dashboard shows `No data`, check that the `environment` variable is set to `gprd`.
> Alert links generated before [runbooks!11820](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/11820) arrived with `var-environment=` empty, which makes every query match nothing.

## References

- [Concurrency limit worker attribute](https://docs.gitlab.com/development/sidekiq/worker_attributes/#concurrency-limit)
