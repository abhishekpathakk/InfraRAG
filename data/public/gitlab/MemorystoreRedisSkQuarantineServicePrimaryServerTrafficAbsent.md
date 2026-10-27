# MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent

## Overview

- This alert fires when the `primary_server` SLI of the `memorystore-redis-sk-quarantine` service reported traffic an hour ago but reports none now, for at least 30m. The signal is absent, not zero.
- The `primary_server` SLI measures operations on the Redis primary of the GCP-managed MemoryStore instance. Its metric comes from the GCP Stackdriver exporter, not from Rails or from the Sidekiq probe. An absent signal therefore usually means the exporter has stopped reporting, not that Redis itself is down.
- The instance backs only the `queues_shard_quarantine` Sidekiq shard. If it is genuinely serving no traffic, quarantined workers are not being enqueued or drained.
- Unlike other Redis instances, this shard can be legitimately idle: it only sees traffic while a worker is routed to quarantine. See [False positives](#false-positives) before treating an absent signal as an incident.
- When this fires, first decide whether the metric pipeline broke (exporter or metric name change) or the shard is genuinely idle.

## Services

- [Memorystore Redis Sidekiq Quarantine overview](../README.md)
- [Service Overview dashboard](https://dashboards.gitlab.net/d/memorystore-redis-sk-quarantine-main/memorystore-redis-sk-quarantine-overview)
- Team that owns the service: [Tenant Services](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/tenant-services/)

## Metrics

- The alert compares the `primary_server` component ops rate against itself one hour earlier: `gitlab_component_ops:rate_5m{component="primary_server",type="memorystore-redis-sk-quarantine"} offset 1h unless <same without offset>`. It fires when the series was present an hour ago but is absent now, for `30m`.
- The underlying metric is `stackdriver_redis_instance_redis_googleapis_com_commands_calls`, scraped from the GCP Monitoring API by the `stackdriver-exporter-memorystore` ArgoCD service and expressed as commands per second.
- Under normal conditions this SLI tracks quarantine-shard enqueue and drain volume. It is bursty by design: the shard holds badly-behaved workers, so traffic tracks whichever worker is currently routed there rather than following a daily cycle.
- Definition: [`metrics-catalog/services/memorystore-redis-sk-quarantine.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/memorystore-redis-sk-quarantine.jsonnet). The `primary_server` SLI itself comes from the shared archetype [`libsonnet/service-archetypes/memorystore-redis-rails-archetype.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/service-archetypes/memorystore-redis-rails-archetype.libsonnet).

## Alert Behavior

- Silence via the [Alertmanager view](https://alerts.gitlab.net/#/alerts?filter=%7Balertname%3D%22MemorystoreRedisSkQuarantineServicePrimaryServerTrafficAbsent%22%7D). Silence only when the absence is confirmed benign — most often when no worker is routed to quarantine.
- There are no automated silencing rules.

## Severities

- **s2**, pages (`alert_type: cause`, `pager: pagerduty`); gprd paging alerts route to Incident.io.
- Confirm severity by checking whether quarantined jobs are actually stuck, rather than treating the absent metric alone as user impact. The shard's `feature_category` is `not_owned` because the workers routed to it change over time — impact depends on which worker is currently quarantined.
- If only the metric is absent while the shard is enqueuing and draining normally, this is a monitoring-pipeline issue, not a user-facing incident — downgrade accordingly.

## Verification

- [Prometheus query that triggered the alert](https://dashboards.gitlab.net/d/memorystore-redis-sk-quarantine-main/memorystore-redis-sk-quarantine-overview): compare `gitlab_component_ops:rate_5m{component="primary_server",type="memorystore-redis-sk-quarantine"}` now vs `offset 1h`.
- Check the raw source metric `stackdriver_redis_instance_redis_googleapis_com_commands_calls{type="memorystore-redis-sk-quarantine"}`. If this is also absent, the problem is the Stackdriver exporter, not Redis.
- Compare against the `rails_redis_client` SLI. If Rails-side traffic (`gitlab_redis_client_requests_total{storage="queues_shard_quarantine"}`) is present while `primary_server` is absent, the instance is serving traffic and the gap is in the GCP metric pipeline.
- Check whether any worker is currently routed to quarantine. If the routing table is empty, zero traffic is expected — see [sidekiq/sharding.md](../../sidekiq/sharding.md).

## Recent changes

- [Recent production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=closed&first_page_size=20)
- [ArgoCD apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) — the Stackdriver exporter is deployed here.
- [config-mgmt MRs](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&state=merged) — MemoryStore instance changes.
- Sidekiq routing changes that add or remove workers from the quarantine shard, which change the shard's baseline traffic.

## Troubleshooting

1. Confirm scope: check the dashboard for which environment and stage is absent.
2. Check whether a worker is still routed to quarantine. If routing was reverted and the shard is now unused, the absence is expected — see [False positives](#false-positives).
3. Check the raw Stackdriver metric (see [Verification](#verification)). If absent, investigate the `stackdriver-exporter-memorystore` ArgoCD service — pod health and logs — rather than Redis.
4. Cross-check the `rails_redis_client` SLI. Present Rails traffic + absent `primary_server` confirms a metric-pipeline gap.
5. If both SLIs are absent, connect to the instance to confirm it is reachable and serving. Retrieve the endpoint and auth as described in [Checking queue depth](../README.md#checking-queue-depth), then run `redis-cli ... info stats` and check `instantaneous_ops_per_sec`.
6. Do not use the `gitlab-exporter` Sidekiq probe to diagnose this alert. That probe feeds `sidekiq_queue_size`, not this SLI; a healthy probe does not rule out a broken Stackdriver pipeline, and vice versa. See [Metrics panels show `No data`](../README.md#metrics-panels-show-no-data) for the probe-side checklist.

## Possible Resolutions

- Metric pipeline broken: restart or roll back the `stackdriver-exporter-memorystore` deployment. Alert recovers once the metric reports again.
- Shard genuinely idle after a routing revert: expected. Silence for the idle period.
- Genuine traffic stop with a worker still routed: restore the client path (revert the offending change) and escalate as a Sidekiq incident if quarantined jobs are stuck.

## Dependencies

- GCP MemoryStore for Redis instance backing `queues_shard_quarantine`, provisioned in [`environments/gprd/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/memorystore.tf) and [`environments/gstg/memorystore.tf`](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/memorystore.tf).
- GCP Stackdriver / Cloud Monitoring API and the `stackdriver-exporter-memorystore` ArgoCD service (metric source for this SLI).
- GitLab Rails and the Sidekiq quarantine shard, which enqueue against and drain this instance.

## Escalation

- Owning team: Tenant Services, `#g_tenant_services` in Slack.
- If quarantined jobs are stuck, coordinate with the owners of whichever worker is currently routed to quarantine — see [sidekiq/sharding.md](../../sidekiq/sharding.md).

## Definitions

- [Alert definition (generated Mimir rules)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/memorystore-redis-sk-quarantine/autogenerated-gitlab-gprd-memorystore-redis-sk-quarantine-service-level-alerts.yml)
- Traffic-cessation alerts can be disabled per SLI via `trafficCessationAlertConfig`; see [Traffic Cessation Alerts](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/metrics-catalog/traffic-cessation-alerts.md). Prefer this over repeated silencing if the shard is expected to idle for long periods.
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

### False positives

- No worker is currently routed to the quarantine shard. The shard exists to isolate specific workers, so an empty routing table means zero traffic by design. This is the most likely cause of a benign firing on this service, and it does not apply to the other MemoryStore Redis instances.
- A quarantined worker was disabled via feature flag (see [disabling a worker](../../sidekiq/disabling-a-worker.md)), stopping the only inflow to the shard.

## Related Links

- [Memorystore Redis Sidekiq Quarantine overview](../README.md)
- [Sidekiq sharding](../../sidekiq/sharding.md)
- [Generic TrafficAbsent and TrafficCessation runbook](../../alerts/TrafficAbsent.md)
- [Related alerts](./)
