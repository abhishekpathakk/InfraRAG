# MemorystoreRedisTracechunksServicePrimaryServerTrafficAbsent

## Overview

- This alert fires when the `primary_server` SLI of the `memorystore-redis-tracechunks` service reported traffic an hour ago but reports none now, for at least 30m. The signal is absent, not zero.
- The `primary_server` SLI measures operations on the Redis primary of the GCP-managed MemoryStore instance. Its metric comes from the GCP Stackdriver exporter, not from Rails. An absent signal therefore usually means the exporter has stopped reporting, not that Redis itself is down.
- TraceChunks stores CI job trace (log) output. If the instance is genuinely serving no traffic, CI job output may be delayed in becoming visible, or in severe cases lost.
- When this fires, first decide whether the metric pipeline broke (exporter or metric name change) or the instance is genuinely idle.

## Services

- [Memorystore Redis TraceChunks overview](../README.md)
- [Service Overview dashboard](https://dashboards.gitlab.net/d/memorystore-redis-tracechunks-main/memorystore-redis-tracechunks-overview)
- Team that owns the service: [Tenant Services](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/tenant-services/)

## Metrics

- The alert compares the `primary_server` component ops rate against itself one hour earlier: `gitlab_component_ops:rate_5m{component="primary_server",type="memorystore-redis-tracechunks"} offset 1h unless <same without offset>`. It fires when the series was present an hour ago but is absent now, for `30m`.
- The underlying metric is `stackdriver_redis_instance_redis_googleapis_com_commands_calls`, scraped from the GCP Monitoring API by the Stackdriver exporter and expressed as commands per second.
- Under normal conditions this SLI tracks CI trace-chunk write/read volume: steady during working hours, lower overnight and at weekends. A drop to no data is abnormal; a drop to low-but-nonzero is not this alert (see [False positives](#false-positives)).
- Definition: [`metrics-catalog/services/memorystore-redis-tracechunks.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/memorystore-redis-tracechunks.jsonnet).

## Alert Behavior

- Silence via the [Alertmanager view](https://alerts.gitlab.net/#/alerts?filter=%7Balertname%3D%22MemorystoreRedisTracechunksServicePrimaryServerTrafficAbsent%22%7D). Silence only when the absence is confirmed benign (for example a known low-traffic window or a scheduled change to the metric pipeline).
- Expected to be rare. It should fire only during a genuine traffic stop or a break in the Stackdriver metric pipeline.
- There are no automated silencing rules.

## Severities

- **s2**, pages (`alert_type: cause`, `pager: pagerduty`); gprd paging alerts route to Incident.io.
- Impact is to CI job trace output for gitlab.com users. Confirm severity by checking whether CI job logs are actually delayed or missing, rather than treating the absent metric alone as user impact.
- If only the metric is absent while CI trace output is healthy, this is a monitoring-pipeline issue, not a user-facing incident — downgrade accordingly.

## Verification

- On the [Service Overview dashboard](https://dashboards.gitlab.net/d/memorystore-redis-tracechunks-main/memorystore-redis-tracechunks-overview), or in Mimir Explore, compare the alert query `gitlab_component_ops:rate_5m{component="primary_server",type="memorystore-redis-tracechunks"}` now vs `offset 1h`.
- Check the raw source metric `stackdriver_redis_instance_redis_googleapis_com_commands_calls{type="memorystore-redis-tracechunks"}`. If this is also absent, the problem is the Stackdriver exporter, not Redis.
- Compare against the `rails_redis_client` SLI. If Rails-side traffic (`gitlab_redis_client_requests_total{storage="trace_chunks"}`) is present while `primary_server` is absent, the instance is serving traffic and the gap is in the GCP metric pipeline.

## Recent changes

- [Recent production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=closed&first_page_size=20)
- [ArgoCD apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged) — the Stackdriver exporter is deployed here.
- [config-mgmt MRs](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&state=merged) — MemoryStore instance changes.

## Troubleshooting

1. Confirm scope: check the dashboard for which environment and stage is absent.
2. Check the raw Stackdriver metric (see [Verification](#verification)). If absent, investigate the `stackdriver-exporter-memorystore` ArgoCD service — pod health and logs — rather than Redis.
3. Cross-check the `rails_redis_client` SLI. Present Rails traffic + absent `primary_server` confirms a metric-pipeline gap.
4. If both SLIs are absent, connect to the instance to confirm it is reachable and serving. See [connecting-to-memorystore-redis.md](../connecting-to-memorystore-redis.md), then run `redis-cli ... info stats` and check `instantaneous_ops_per_sec`.
5. If the instance is genuinely idle, find the client: check for a recent change that stopped CI trace-chunk writes (application, routing, or feature flag).

## Possible Resolutions

- Metric pipeline broken: restart or roll back the `stackdriver-exporter-memorystore` deployment. Alert recovers once the metric reports again.
- Genuine traffic stop: restore the client path (revert the offending change). Escalate as a CI incident if job trace output is affected.
- Confirmed benign low-traffic window: silence for the window; consider tuning (see [Definitions](#definitions)).

## Dependencies

- GCP MemoryStore for Redis instance (`tracechunks-redis`).
- GCP Stackdriver / Cloud Monitoring API and the `stackdriver-exporter-memorystore` ArgoCD service (metric source).
- GitLab Rails, which reads and writes CI trace chunks against this instance.

## Escalation

- Owning team: Tenant Services, `#g_tenant_services` in Slack.
- For CI job-output impact, coordinate with the `continuous_integration` feature-category owners.

## Definitions

- [Alert definition (generated Mimir rules)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/memorystore-redis-tracechunks/autogenerated-gitlab-gprd-memorystore-redis-tracechunks-service-level-alerts.yml)
- Traffic-cessation alerts can be disabled per SLI via `trafficCessationAlertConfig`; see [Traffic Cessation Alerts](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/metrics-catalog/traffic-cessation-alerts.md). Prefer this over silencing if the instance is expected to idle regularly.
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

### False positives

- A genuine low-traffic window (overnight, weekend, holiday) where CI trace-chunk volume drops to zero.
- A scheduled maintenance period with no CI activity.

## Related Links

- [Memorystore Redis TraceChunks overview](../README.md)
- [Connecting to the MemoryStore instance](../connecting-to-memorystore-redis.md)
- [Generic TrafficAbsent and TrafficCessation runbook](../../alerts/TrafficAbsent.md)
- [Related alerts](./)
