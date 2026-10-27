# component_saturation_slo_out_of_bounds:redis_memory

## Overview

This alert is triggered when the `redis_memory` saturation resource for the Redis Sidekiq service goes out of its SLO bounds. This resource measures how much of a node's total memory Redis is using. Note that the Redis Sidekiq is a [Sentinel](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/) and not a [Cluster](https://redis.io/docs/latest/operate/oss_and_stack/management/scaling/) like Redis SharedState; the `shard` label in this case identifies the Redis deployment name, not a cluster shard.

As Redis memory saturates node memory, the likelihood of OOM kills (possibly to the Redis process itself) increases. Known causes include:

- A worker flooding a queue. Most often this is a worker whose jobs are **deferred or throttled** (to relieve pressure elsewhere) but then accumulate in Redis until memory is exhausted. This is the most common cause and the pattern behind past redis-sidekiq memory incidents.
- Large Sidekiq queue backlogs (e.g. an unbounded `default` queue).
- Very large job payloads delivered via Sidekiq.
- Memory fragmentation increasing RSS beyond the logical dataset size.

The threshold is kept deliberately low to leave headroom for short-term spikes from Redis snapshotting (copy-on-write), which grows with the rate of change in Redis.

## Services

Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Metrics

This alert is based on the `redis_memory` saturation point, which compares Redis memory usage (`redis_memory_used_rss_bytes` / `redis_memory_used_bytes`) against total node memory (`node_memory_MemTotal_bytes`), per node.

This resource has a **soft** and a **hard** SLO threshold. The thresholds are kept intentionally low to leave headroom: Redis RDB snapshots can put short-term memory pressure on a node via copy-on-write (which grows with the rate of change in Redis), so alerting well before the node is full gives due warning before that pressure can tip the node over.

The exact query and threshold values are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Alert Behavior

This alert fires when saturation stays above the **hard** SLO threshold for the rule's `for` duration (`gitlab_component_saturation:ratio{component="redis_memory"} > slo:max:hard:...`). At that point the resource is close to its capacity limit and at risk of OOM kills.

The **soft** SLO is lower and is used for capacity-planning warnings and dashboard banding rather than this paging alert.

There are no automated silencing rules. Silence only if the reported value is confirmed inaccurate and a corrective change is due for deployment soon.

The alert expression and `for` duration are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Severities

**s2**, pages (`alert_type: cause`, `pager: pagerduty`). The `pager: pagerduty` label marks the alert as paging; since the GitLab.com EOC/IMOC cutover, `gprd` paging alerts route to Incident.io.

Saturation past the hard threshold risks OOM kills of the Redis process — a significant availability event for Sidekiq.

## Verification

- Identify the saturated node/deployment (start here):
  - [redis_memory saturation dashboard](https://dashboards.gitlab.net/d/alerts-sat_redis_memory?var-environment=gprd&var-type=redis-sidekiq&var-stage=main) (`uid: alerts-sat_redis_memory`): find which node or Redis deployment is over the SLO bound.
  - [redis-sidekiq: Overview](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq-overview)

- Sidekiq workload (attribute growth to a specific deployment/queue/worker):
  - [Queue length](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail?orgId=1&from=now-1h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all&viewPanel=panel-922970012): Queue length of workers is useful to for identifying a potential worker with a large set of enqueued jobs.
  - [sidekiq: Worker Detail](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail): per-worker enqueue rate, queue size, and execution time; useful for spotting a worker flooding a queue and job processing rate.
  - [sidekiq: Shard Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail): drill down from a saturated deployment to its queues and workers. The `Job Argument Size by Worker` panel links out to a Kibana table of per-worker argument byte size for the selected shard (measured at job execution time, `args` only); useful as a reference for per-worker volume and for mapping `destination_shard_redis` to worker.
  - [sidekiq: Queue Detail](https://dashboards.gitlab.net/d/sidekiq-queue-detail/sidekiq-queue-detail): per-queue enqueue/execution rates and backlog.
  - [Skipped jobs](https://dashboards.gitlab.net/goto/efq0333mk0t8gd?orgId=1): the `sidekiq_jobs_skipped_total` counter tracks jobs that are **deferred** or **dropped** rather than executed (labels: `worker`, `action` = `deferred`/`dropped`, `reason` = `feature_flag`/`database_health_check`). A worker with a high deferred rate is accumulating its backlog in redis-sidekiq and is the prime suspect for this saturation alert.
  - [Enqueue rate](https://dashboards.gitlab.net/goto/afq02lkmgk268d?orgId=1): the `sidekiq_enqueued_jobs_total` counter is incremented once per job enqueued by a Sidekiq client (labels include `worker`, `queue`, `feature_category`, `scheduling` = `immediate`/`delayed`, and `destination_shard_redis`). Pair it with the skipped-jobs counter to spot a worker flooding a queue: a high enqueue rate combined with deferred execution is the classic pattern behind this alert. The `destination_shard_redis` label maps a worker directly to the saturated deployment via the [Troubleshooting](#troubleshooting) deployment-to-shard table.

- Rule out other causes:
  - Compare [redis_memory_used_bytes](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq3a-overview?orgId=1&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-shard=$__all&var-shard-2=$__all&viewPanel=panel-85) vs [redis_memory_used_rss_bytes](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq3a-overview?orgId=1&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-shard=$__all&var-shard-2=$__all&viewPanel=panel-87) to identify fragmentation.
  - [host stats](https://dashboards.gitlab.net/d/bd2Kl9Imk/host-stats) (per-host): drill into CPU/memory/IO for the affected node once identified.

- Logs: [system logs](https://log.gprd.gitlab.net/goto/80a1ff609f91b0fb2b770a3a70784be0)

## Recent changes

Redis Sidekiq runs on VMs managed via Chef. Recent configuration changes are found in the [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests) and in the service's Chef roles, e.g. [gprd-base-db-redis-server-sidekiq.json](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-redis-server-sidekiq.json).

## Troubleshooting

Under normal operation Redis Sidekiq sits well within its memory budget. Saturation almost always traces back to a single worker flooding a queue, most often because its jobs are being **deferred** rather than executed (the pattern behind past redis-sidekiq memory incidents). Prioritize identifying that worker.

1. Identify which node / Redis deployment is saturated:
   - [redis_memory saturation dashboard](https://dashboards.gitlab.net/d/alerts-sat_redis_memory?var-environment=gprd&var-type=redis-sidekiq&var-stage=main).
2. Map the saturated Redis deployment to its `destination_shard_redis` shard:

   | Redis deployment                      | Redis Destination Shard   |
   |---------------------------------------|---------------------------|
   | `redis-sidekiq-NN-db-gprd` (plain)    | `main`                    |
   | `redis-sidekiq-catchall-a-NN-db-gprd` | `queues_shard_catchall_a` |
   | `redis-sidekiq-catchall-b-NN-db-gprd` | `queues_shard_catchall_b` |

   The **Job Argument Size by Worker** panel on the [sidekiq: Shard Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail) dashboard links to a Kibana table that shows both `destination_shard_redis` and the actual `sidekiq_shard` per worker, a handy reference for this mapping.

3. Find if a worker is driving the growth. Precise attribution is inherently limited: there is no full point-in-time snapshot of queue contents, and job *count* is not a reliable proxy for memory because per-job payload size varies. Treat the signals below as ways to identify a *suspect*, not conclusive proof:
   - **Check for deferred jobs first.** List currently deferred workers. A worker with `run_sidekiq_jobs_{WorkerName}` disabled will accumulate backlog in the redis-sidekiq queue.

     ```shell
     /chatops gitlab run feature list --match run_sidekiq_jobs
     ```

     The [sidekiq_jobs_skipped_total](https://dashboards.gitlab.net/goto/efq0333mk0t8gd?orgId=1) counter (labels `worker`, `action` = `deferred`/`dropped`, `reason` = `feature_flag`/`database_health_check`) confirms which workers are actually being deferred or dropped and at what rate — a non-zero `deferred` rate identifies the worker filling the queue. The `SidekiqJobsSkippedTooLong` alert fires when a worker is deferred via feature flag for over 3 hours, a common sign of a forgotten `run_sidekiq_jobs_{WorkerName}` flag.

   - Use the [sidekiq: Worker Detail](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail) dashboard to check a worker's enqueue rate, queue size, and execution time. Drill down from [sidekiq: Shard Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail) (left-click a job line to open Worker Detail) to find which worker is flooding the saturated shard's queues.
   - Inspect what is currently running with the Ruby snippets in [Sidekiq inspection](../../sidekiq/sidekiq-inspection.md) (`sudo gitlab-rails console` + `Sidekiq::Workers.new`).
4. If no worker is implicated, check other causes:
   - A sharp, short-lived spike that is not matched by dataset growth points to a Redis RDB snapshot, where a high rate-of-change drives copy-on-write memory overhead. Correlate the spike timing against snapshot activity rather than assuming dataset growth.
   - Memory fragmentation: compare [redis_memory_used_rss_bytes](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq3a-overview?orgId=1&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-shard=$__all&var-shard-2=$__all&viewPanel=panel-87) to [redis_memory_used_bytes](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq3a-overview?orgId=1&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-shard=$__all&var-shard-2=$__all&viewPanel=panel-85). Their ratio ([redis_mem_fragmentation_ratio](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22f93%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22redis_mem_fragmentation_ratio%7Btype%3D%5C%22redis-sidekiq%5C%22,%20env%3D%5C%22gprd%5C%22%7D%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22,%22hide%22:false%7D%5D,%22range%22:%7B%22from%22:%22now-6h%22,%22to%22:%22now%22%7D,%22compact%22:false%7D%7D&orgId=1)) baselines differently per instance, so judge it against that node's own history rather than a fixed value. A high but flat ratio is usually benign. Fragmentation only matters when absolute RSS trends toward node memory. Dataset growth is the more common cause here.
   - Stuck or oversized keys driving dataset growth.
   - For sustained or recurring saturation, run offline key-space analysis of a Redis RDB dump (see [Memory space analysis with cupcake-rdb](../../redis/memory-space-analysis-cupcake-rdb.md)).
5. Confirm whether a kernel OOM kill has already occurred on the affected node: search the [system logs](https://log.gprd.gitlab.net/goto/80a1ff609f91b0fb2b770a3a70784be0) in Kibana for `oom-killer` or `Out of memory: Killed process` messages, scoped to the affected node. For events older than the index retention, check `dmesg` or persisted kernel logs on the node directly. This is distinct from Redis hitting its own `maxmemory` limit.

## Possible Resolutions

> [!WARNING]
> Before dropping a worker's jobs, sync with the team or someone familiar with the worker to confirm it is safe as discarded jobs are not recoverable. The [Disabling a worker](../../sidekiq/disabling-a-worker.md#1-using-feature-flags-via-chatops) flowchart helps decide whether a worker's backlog can be dropped.

- If a single worker is flooding a queue, the lever that actually relieves memory pressure is to **drop** its jobs via ChatOps. Deferring (`run_sidekiq_jobs_{WorkerName}`) keeps the backlog in Redis, so it does not help here and can thunder-herd on re-enable; dropping (`drop_sidekiq_jobs_{WorkerName}`) discards the jobs and frees the memory. Only drop jobs that can be safely discarded (see [Disabling a worker](../../sidekiq/disabling-a-worker.md) for the full drop-vs-defer flow):

  ```shell
  # drop: discard jobs entirely (use only when the backlog can be safely thrown away)
  /chatops gitlab run feature set drop_sidekiq_jobs_WorkerName true --ignore-feature-flag-consistency-check --ignore-production-check
  ```

- Scale up (resize) node memory when the working set has legitimately grown, or as a short-term mitigation to restore memory headroom while the underlying cause is investigated. Redis Sidekiq runs on VMs, so this is a node/VM resize, not a Redis Cluster scaling operation. The resize is a **manual operation done under a change request**, because Terraform will not apply a `machine_type` change on its own: the redis-sidekiq instances are created from the external [`generic-stor` module](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/google/generic-stor) (Terraform source `ops.gitlab.net/gitlab-com/generic-stor/google`), whose `lifecycle` block sets `ignore_changes = [..., machine_type]`, and each module instantiation in config-mgmt (`environments/gprd/main.tf`) passes `allow_stopping_for_update = false`.
  - Pick the right deployment: each redis-sidekiq deployment has its own key (`redis-sidekiq`, `redis-sidekiq-catchall-a`, `redis-sidekiq-catchall-b`) and they can differ in size. Resize the deployment you identified in the [Troubleshooting](#troubleshooting) section (the deployment-to-shard mapping table), not necessarily the plain `redis-sidekiq` key.
  - Before operating on any node, check its role with `ssh <vm-fqdn> -- sudo gitlab-redis-cli ROLE`. Operate on **replicas first**; for the **primary**, perform a Sentinel failover to a healthy replica first, then resize the demoted (now-replica) old primary. This is the established pattern for redis-sentinel VM operations (see the [Redis survival guide for SREs](../../redis/redis-survival-guide-for-sres.md)). Track each production node's resize under its own change issue in [gitlab-com/gl-infra/production](https://gitlab.com/gitlab-com/gl-infra/production).
  - Resize the VM directly with the `gcloud` CLI: stop the instance, set the machine type, then start it.

    ```shell
    gcloud compute instances stop <VM_NAME> --zone=<ZONE> --project=<PROJECT_ID>
    gcloud compute instances set-machine-type <VM_NAME> --machine-type=<NEW_MACHINE_TYPE> --zone=<ZONE> --project=<PROJECT_ID>
    gcloud compute instances start <VM_NAME> --zone=<ZONE> --project=<PROJECT_ID>
    ```

  - After the VM is back up, verify it: tail the startup script for chef errors with `gcloud compute instances tail-serial-port-output <VM_NAME> --project=<PROJECT_ID> --zone=<ZONE> | grep startup-script`, confirm the node's role with `gitlab-redis-cli ROLE`, and check service Apdex and error rates on the [redis-sidekiq: Overview](https://dashboards.gitlab.net/d/redis-sidekiq-main/redis-sidekiq-overview) dashboard.
  - Backport the change to [config-mgmt](https://gitlab.com/gitlab-com/gl-infra/config-mgmt) to keep the declared state in sync: update the `machine_types` entry for the affected deployment in [environments/gprd/variables.tf](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/variables.tf). Because Terraform ignores `machine_type`, an `atlantis plan` after the backport should be a no-op. See [config-mgmt!14110](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/14110) (bump size of `redis-sidekiq-catchall-b`) as an example.
  - The node's Redis software/config is managed separately via the [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests) [gprd-base-db-redis-server-sidekiq.json](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-redis-server-sidekiq.json) role, which does not control VM size.
- Address the upstream cause of growth (queue backlog, large job payloads, fragmentation).
- For sustained growth, revisit capacity planning for the affected deployment.

## Dependencies

Internal and external dependencies which could potentially cause this alert:

- **Sidekiq application / workers**: the most common cause: a single worker flooding a queue, especially when its jobs are **deferred** via `run_sidekiq_jobs_*` ChatOps flags and accumulate in Redis. Also large job payloads and unbounded queue backlogs.
- **Redis**: internal memory behavior: RDB snapshot copy-on-write under a high rate-of-change, and memory fragmentation (RSS exceeding the logical dataset size).
- **Underlying node/VM memory**: total node memory is the saturation denominator; an undersized VM raises the ratio for the same Redis footprint.

## Escalation

If the issue cannot be resolved quickly, escalate to the appropriate engineering or operations team for further investigation. Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Definitions

The definition for this alert can be found at:

- [saturation-monitoring/redis_memory.libsonnet](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/saturation-monitoring/redis_memory.libsonnet)
- [redis-sidekiq saturation alerts (gprd)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/redis-sidekiq/autogenerated-gitlab-gprd-redis-sidekiq-saturation-alerts.yml)
- [redis-sidekiq saturation alerts (gstg)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/redis-sidekiq/autogenerated-gitlab-gstg-redis-sidekiq-saturation-alerts.yml)

## Related Links

- [Redis Sidekiq service](../README.md)
- [Sidekiq survival guide for SREs](../../sidekiq/sidekiq-survival-guide-for-sres.md)
- [Disabling a worker](../../sidekiq/disabling-a-worker.md): how to drop a misbehaving Sidekiq worker
- [Sidekiq inspection](../../sidekiq/sidekiq-inspection.md): inspecting Sidekiq running state from the Rails console
- [Memory space analysis with cupcake-rdb](../../redis/memory-space-analysis-cupcake-rdb.md): offline key-space analysis of Redis RDB dumps
