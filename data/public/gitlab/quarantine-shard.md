# The Sidekiq quarantine shard and its dedicated MemoryStore Redis (`memorystore-redis-sk-quarantine`)

Reference document for the Sidekiq `quarantine` shard and the GCP MemoryStore Redis instance
backing it. This is not a runbook.

If you are responding to an alert, go to the
[`memorystore-redis-sk-quarantine` runbook](../memorystore-redis-sk-quarantine/README.md)
instead. That document covers checking queue depth, relieving memory pressure, and the
symptom/cause/action table. This document records the constraints and failure modes that
change how you operate or extend the shard.

For the generic Sidekiq sharding procedure, see [sharding.md](sharding.md). For Redis at
GitLab generally, see the
[Redis survival guide for SREs](../redis/redis-survival-guide-for-sres.md).

## Why the quarantine shard has its own Redis

The `quarantine` shard exists to isolate badly-behaved Sidekiq workers. Until mid-2026 it
only isolated the *Kubernetes deployment* — it still shared the `redis-sidekiq` Sentinel
instance with seven or more other shards (`memory-bound`, `database-throttled`,
`gitaly-throttled`, `import-shared-storage`, `elasticsearch`, `low-urgency-cpu-bound`, and
all the `urgent_*` shards). Only `catchall` and `catchall_b` had dedicated Redis instances
(`redis-sidekiq-catchall-a` and `redis-sidekiq-catchall-b`).

That made the isolation incomplete. A worker quarantined for flooding a queue could still
grow `redis-sidekiq` without bound and cause OOM-driven queueing delays for every
co-located shard — the exact cross-contamination the shard was meant to prevent.

Three incidents drove the work, all involving `AuditEvents::AuditEventStreamingWorker`
causing Redis OOM or queueing delays on `catchall_b`: INC-10096 (S1), INC-10084 and INC-985.

Analysis and the isolation proposal are in
[tenant-services/team#432](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/432),
under epic
[tenant-services&56](https://gitlab.com/groups/gitlab-com/gl-infra/tenant-scale/tenant-services/-/work_items/56).

## Why MemoryStore instead of a Sentinel Redis

Both existing dedicated Sidekiq Redis instances (`redis-sidekiq-catchall-a`,
`redis-sidekiq-catchall-b`) are Sentinel-based VMs managed by Chef, so choosing GCP
MemoryStore was a deliberate departure from that pattern. The evaluation is
[tenant-services/team#439](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/439).

MemoryStore removes the operational cost of owning three Sentinel nodes per instance, for a
workload whose entire purpose is blast-radius containment and which gains no isolation
benefit from self-management. It also followed the completed `redis-tracechunks` migration.

Three behaviours established during that evaluation change how the instance is operated:

* **`noeviction` does not cap queue growth gracefully.** At saturation writes are rejected
  with `OOM command not allowed when used memory > 'maxmemory'` and nothing is evicted.
  Reads, `LLEN` and `BRPOP`/`BRPOPLPUSH` keep working, so a full instance rejects new work
  but still drains rather than deadlocking. Rejection is payload-size dependent rather than
  a clean cliff, so sizing and early alerting still matter.
* **Failover is a bounded, retryable blip** — roughly 10.7s of client-visible write outage,
  surfacing as `READONLY You can't write against a read only replica`, with no job loss.
* **Resize is not an incident-time lever.** Resizing under load took about 21 minutes versus
  about 33s idle, and is non-disruptive but dominated by control-plane node replacement
  rather than data volume. **"Just resize it" is a 20-minute lever, not an instant one.**

`noeviction` must be set at instance creation: MemoryStore blocks `CONFIG SET`, so the
eviction policy cannot be changed on a live instance.

## What was built

Provisioning is [tenant-services/team#440](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/440).

| | gstg | gprd |
| --- | --- | --- |
| Size | 5 GiB | 40 GiB |
| Tier | `STANDARD_HA`, `replica_count=1` | `STANDARD_HA`, `replica_count=1` |
| Eviction policy | `noeviction` | `noeviction` |
| Terraform | config-mgmt!14469 | config-mgmt!14670 |
| Change request | production#22361 | production#22450, production#22521 |

Instance definitions live in
[`environments/gstg/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/memorystore.tf)
and
[`environments/gprd/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/memorystore.tf).

gprd was sized at 40 GiB to clear the 35 GiB memory excursion observed on
`redis-sidekiq-catchall-b` during a 2026-05-19 near-miss, with headroom so the slow resize
path is not needed during an incident. gprd also runs RDB snapshots hourly
(`rdb_snapshot_period ONE_HOUR`) to match the on-disk posture of the Sentinel
`redis-sidekiq` clusters.

Wiring spans two configuration systems, because not every Sidekiq client runs in
Kubernetes. `queues_shard_quarantine` is defined as a `redisYmlOverride` in
`k8s-workloads/gitlab-com` for pods, and as a `redis_yml_override` in `chef-repo` for
non-Kubernetes nodes. Credentials come from Vault at
`env/{gstg,gprd}/ns/gitlab/memorystore-redis-sidekiq-quarantine`, surfaced to pods through
the ExternalSecret `gitlab-memorystore-redis-sidekiq-quarantine-credential-v1`. Routing is
pinned with `SIDEKIQ_MIGRATED_SHARDS` rather than left on the
`sidekiq_route_to_queues_shard_quarantine` feature flag.

`AuditEvents::AuditEventStreamingWorker` and `Analytics::SnowplowEmitterWorker` are the
workers routed to the shard.

## Why the shard runs 8 threads per pod, not 15

The first gprd cutover attempt was rolled back and caused **INC-12023** and **INC-12026**.

`AuditEvents::AuditEventStreamingWorker` is CPU-bound, at roughly 100ms of CPU time per job.
At 15 threads per pod, CPU-bound threads competed for the same pod's Ruby GVL and throughput
stalled at about 1.7k despite roughly 3k threads being theoretically available. The
application-level concurrency-limit middleware compounded it: the limit is computed as a
percentage of `maxReplicas x concurrency`, so moving the worker to a shard with a smaller
total thread pool than `catchall_b` also shrank its effective limit.

The retry halved threads per pod and doubled the pod ceiling, spreading roughly the same
total thread budget across more, smaller pods:

| Setting | First attempt | After retry |
| --- | --- | --- |
| `concurrency` (threads per pod) | 15 | 8 |
| `keda.minReplicaCount` | 10 | 20 |
| `keda.maxReplicaCount` | 200 | 400 |

The current values and a comment recording the reason are in
`releases/gitlab/values/gprd.yaml.gotmpl` in `k8s-workloads/gitlab-com`.

**The general lesson: for a CPU-bound Sidekiq worker, add pods rather than threads.** Packing
threads into fewer pods trades GVL contention for no extra throughput.

## How the shard is observed

Three independent metric sources cover this shard. Confusing them wastes time during an
incident, because each fails separately.

1. **GCP-side instance metrics** — memory, ops/sec, connected clients, evictions — come from
   the GCP Monitoring API, scraped by the `stackdriver-exporter-memorystore` ArgoCD service.
   One deployment covers every MemoryStore instance; the `type` label is derived per
   `instance_id`. This is the source for the `primary_server` SLI.
2. **Sidekiq queue-depth and job-state metrics** — `sidekiq_queue_size`, `sidekiq_jobs_*`,
   retry and schedule set backlogs — come from a standalone `gitlab-exporter` Kubernetes
   Deployment running only the Sidekiq probe, pointed at the remote MemoryStore endpoint.
   Sentinel-based instances run this probe co-located on the Redis VM via Chef, but
   MemoryStore is managed and has no VM to co-locate on, so it runs as the ArgoCD service
   [`services/gitlab-exporter-sk-quarantine/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/gitlab-exporter-sk-quarantine)
   in the `gitlab` namespace. Its configuration gotchas are documented as comments in that
   service's `values.yaml`; the most consequential is `redis_enable_client: false`, because
   MemoryStore disables the Redis `CLIENT` command and without the flag every scrape fails
   with `ERR unknown command 'client'`.
3. **Rails-side client metrics** — `gitlab_redis_client_requests_total{storage="queues_shard_quarantine"}`
   — come from the application. Cross-checking these against the `primary_server` SLI
   distinguishes a broken metric pipeline from a genuinely idle shard.

The shard is **idle by design** whenever no worker is routed to it, so an absent traffic
signal is frequently benign here in a way it is not for other Redis instances. See
[MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent](../memorystore-redis-sk-quarantine/alerts/MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent.md).

### Why the queueing apdex target is 0.95

The `sidekiq_queueing` apdex target for this shard is held at `0.95`, below the service
default of `0.995`. The override is in
`metrics-catalog/services/sidekiq.jsonnet` under
`monitoring.shard.overrides.sidekiq_queueing.thresholds`.

The strict default paged repeatedly on expected behaviour (INC-12509, INC-12576). The shard
holds bursty workers by design; it is pinned at its HPA ceiling, so there is no headroom to
absorb a burst faster, and it runs a single worker, so one worker's burst is the whole
shard's apdex. A backlog alone is not an incident here. `0.95` still catches the case that
matters — jobs not being picked up at all.

## Known open defects

* [tenant-services/team#451](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/451)
  — Sidekiq job logs emit an incorrect `json.shard` value for some jobs. `json.queue` is
  reliable; `json.shard` is not. Do not trust `json.shard` alone to determine where a job
  executed.
* [tenant-services/team#459](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/459)
  — during the routing rollout roughly 400 jobs were enqueued to `main` Redis while
  carrying `"store":"queues_shard_quarantine"` and
  `"meta.sidekiq_destination_shard_redis":"main"`. One-off; did not recur on rollback and
  retry. Root cause not yet found.

## Outstanding isolation work

Redis isolation is complete. The dedicated PgBouncer pool for the shard is not: the
quarantine shard still shares database connection pools with all other non-urgent shards, so
a worker that saturates the pool through long-running queries or idle-in-transaction
connections can still starve them. That work needs a DBRE counterpart and is tracked in
[database-team/team-tasks#639](https://gitlab.com/gitlab-org/database-team/team-tasks/-/work_items/639),
the last open exit criterion on epic
[tenant-services&56](https://gitlab.com/groups/gitlab-com/gl-infra/tenant-scale/tenant-services/-/work_items/56).

Job deduplication and idempotency keys remain on `redis-cluster-queues-meta`, shared
globally, so a stuck deduplication lock for a quarantined worker can still block enqueues
for that worker class everywhere.

## Replicating this for another Sidekiq shard

There is no step-by-step procedure here on purpose — a cutover runbook would drift from the
configuration it describes. The merge request set recorded in
[tenant-services/team#440](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/440)
is the procedural record, and [sharding.md](sharding.md) covers the generic Sidekiq sharding
process.

What is worth carrying forward:

* Wire both `k8s-workloads/gitlab-com` and `chef-repo`. Sidekiq clients exist outside
  Kubernetes, and missing the Chef side leaves those nodes pointed at the old instance.
* Land provisioning, wiring and observability ahead of the change window. Only the routing
  cutover needs to happen inside it.
* Stand the observability up *before* cutting over. Queue-depth panels silently read from
  the old shared instance otherwise, which is how the exporter gap in
  [tenant-services/team#462](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/tenant-services/team/-/work_items/462)
  went unnoticed until cutover debugging.
* Decide the eviction policy at creation. MemoryStore blocks `CONFIG SET`.
* Check the worker's CPU profile before choosing a concurrency value. See
  [Why the shard runs 8 threads per pod](#why-the-shard-runs-8-threads-per-pod-not-15).

### Second worked example: a Redis store rather than a queue shard

[tenant-services&72](https://gitlab.com/groups/gitlab-com/gl-infra/tenant-scale/tenant-services/-/work_items/72)
reused the same MemoryStore provisioning pattern to move Sidekiq concurrency-limit deferred
jobs off `redis-cluster-shared-state` onto
[`memorystore-redis-concurrency-limit`](../memorystore-redis-concurrency-limit/README.md).

That instance backs a Rails Redis *store* (`Gitlab::Redis::ConcurrencyLimit`), not a Sidekiq
queue shard. It therefore needs no `SIDEKIQ_SHARD_NAME`, no `SIDEKIQ_MIGRATED_SHARDS` entry and
no routing rules. The cutover used `MultiStore` dual-write behind feature flags instead of a
routing change.
