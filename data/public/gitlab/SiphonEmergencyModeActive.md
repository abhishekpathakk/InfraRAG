# SiphonEmergencyModeActive

## Overview

Fires when a Siphon producer has had **emergency mode** (called *failover mode* in the Siphon code, config and logs) active continuously for more than one hour.

Failover mode is a fallback write path: when the producer finds NATS JetStream unhealthy and `queueing.failover_storage` is configured, it stops publishing to NATS and writes replication events to durable storage (GCS, S3 or file) instead. Nothing is lost, the events are durably stored and can be replayed. But while it's on:

- The ClickHouse consumers receive no events, so every table fed by the affected producer stops advancing. Users querying that data see stale results.
- An object storage backlog accumulates. The longer emergency mode stays on, the longer the drain afterwards.

There is **no operator toggle**: the producer enters failover on its own when NATS is unhealthy, and exits automatically once NATS is healthy again (it polls every `recovery_poll_seconds`, default 30s), draining the backlog into NATS before resuming replication. An hour is long enough that a transient flip during a NATS blip or a producer deploy won't page. If it's still on after an hour, NATS hasn't recovered, or the producer can't confirm NATS health (e.g. the main stream or NATS object-store bucket can't be read).

The PostgreSQL replication slot keeps advancing in emergency mode (the LSN is still acked once events are durably buffered), so this alert does **not** imply WAL accumulation on the Patroni primary. If WAL is also accumulating, expect [SiphonLogicalReplicationSlotLagHigh](./SiphonLogicalReplicationSlotLagHigh.md) to fire too, and treat that as the more urgent of the two.

## Services

- [Siphon Service](../README.md)
- Owned by [Platform Insights](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/)
- Depends on NATS JetStream, whose health is usually why emergency mode engaged.

## Metrics

- `siphon_failover_mode_active`: boolean gauge, `1` while emergency mode is active.
- Source: Siphon producer pods in the `siphon` namespace on the `orbit-*` clusters, scraped into the `analytics-eventsdot` Mimir tenant.
- Aggregated with `max by (environment, app_id, cluster)`, so we get one alert per producer rather than one per pod.
- Siphon's metrics in this tenant carry `env="orbit-prd"` / `env="orbit-stg"` rather than the `gprd` / `gstg` the rest of the fleet uses, and the alertmanager route feeding incident.io matches `env=~"gprd|ops|thanos|production"`. The expression therefore derives a fleet-standard `env` from `cluster` via `label_replace`. Without it this alert would only reach Slack despite being an `s2` with `pager: pagerduty`. Keep the `orbit-(prd|stg)` regex in step with the clusters we run, a cluster outside it won't page.
- Threshold: `== 1` sustained for `1h`.
- Normal behaviour: flat `0`. Any sustained `1` is a real fallback state, not noise.

## Alert Behavior

- Clears automatically once emergency mode is off and the gauge returns to `0`.
- `for: 1h` requires the condition to hold **continuously**. A producer restart (in-process or pod) briefly resets the gauge and the pending timer, so a producer that keeps restarting while in emergency mode may never fire. Check the metric directly if you suspect that.
- Silence only for the duration of a Change Request for planned NATS maintenance, not indefinitely.
- Should be rare. Emergency mode is not part of steady-state operation.
- [Previous incidents tagged with this alert](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&search=SiphonEmergencyModeActive)

## Severities

- Default: `s2`, `pager: pagerduty`. It pages because the failure is invisible downstream: ClickHouse looks healthy, it's just not receiving anything, so it needs an active push rather than a channel notification.
- **Escalate to `s1`** if NATS is unhealthy with no sign of recovery, if `SiphonLogicalReplicationSlotLagHigh` is firing on the same cluster (WAL accumulation on a production primary is the bigger risk), or if the backlog is large enough that the drain will exceed the freshness expectations of the downstream data.

## Verification

- [Siphon Producers dashboard](https://dashboards.gitlab.net/d/ahfvxhn/siphon-producers)
- [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon)
- Kibana: [production](https://log.gprd.gitlab.net/app/r/s/6LMBY) / [staging](https://nonprod-log.gitlab.net/app/r/s/qLnJb)

Which producers are affected:

```promql
max(siphon_failover_mode_active{cluster=~"orbit-.*",namespace="siphon"}) by (environment, app_id)
```

How long each has been in emergency mode (seconds, over the last 24h):

```promql
sum_over_time(
  max(siphon_failover_mode_active{cluster=~"orbit-.*",namespace="siphon"}) by (environment, app_id)[24h:1m]
) * 60
```

## Recent changes

- [Recent Siphon changes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=updated_desc&state=opened&label_name%5B%5D=Service%3A%3ASiphon)
- Producer config and deployments live on the `orbit-prd` / `orbit-stg` clusters in the `siphon` namespace. Roll back via the usual Kubernetes rollback.
- See also [Producer in failover mode](../README.md#producer-in-failover-mode-nats-unavailable) in the service runbook.

## Troubleshooting

1. **Identify the producer.** The `app_id` label names it.

1. **Check NATS JetStream health first.** Emergency mode cannot be turned off by hand; it ends automatically once NATS is healthy. See the [NATS runbook](../../nats/README.md).

1. **Check the producer pods.** Look for `entering failover mode: NATS unreachable, buffering CDC to durable storage` and, once NATS is back, `NATS recovered; exiting failover mode and restarting siphon core`.

   ```shell
   glsh kube use-cluster orbit-prd --no-proxy
   kubectl get pods -n siphon -o wide
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=200
   ```

1. **Size the backlog.** The in-flight backlog is `siphon_failover_writes_total - siphon_failover_drain_published_total`. A large backlog replayed into a still-fragile NATS can fail NATS health again and push the producer back into emergency mode.

1. **Watch the automatic drain once NATS is healthy.** No action is needed to start it; a `kubectl rollout restart` only skips the up-to-30s recovery poll. Replication (and the PostgreSQL slot) is paused while the drain runs. `siphon_failover_drain_errors_total` rising or `drain failover store:` in the logs means drain runs are failing; repeated failures eventually crash-loop the producer, at which point WAL starts accumulating on the primary.

1. **Verify the downstream caught up.** Check that the ClickHouse tables fed by this producer have advanced past the gap and that `siphon_failover_mode_active` is back to `0`.

## Possible Resolutions

- No prior incidents yet; this alert is new. Add links here as we accumulate production experience.
- [All previous incidents involving Siphon](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3ASiphon)

## Dependencies

- NATS JetStream: the primary write path emergency mode bypasses.
- Object storage: the fallback write path holding the backlog.
- Siphon producer (`postgres-producer-*` pods in the `siphon` namespace).
- ClickHouse consumers: starved of events while emergency mode is on.

## Escalation

- Primary contact: `#g_analytics_platform_insights`. Most context: `@ahegyi`, `@arun.sori`, `@ankitbhatnagar`.
- If NATS is the underlying problem and there's no response from the primary contacts, escalate through the usual EOC path.

## Definitions

- [Alert definition (Jsonnet source)](../../../libsonnet/alerts/siphon-emergency-mode-alerts.libsonnet)
- [Generator wiring](../../../mimir-rules-jsonnet/siphon-emergency-mode-alerts.jsonnet)
- The only tunable is the `1h` `for:` window. Shorten it if an hour of staleness is already too much for the downstream consumers; lengthen it if legitimate NATS maintenance routinely runs longer.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/siphon/alerts/SiphonEmergencyModeActive.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related Siphon alerts](./)
- [Siphon service overview](../README.md)
- [SiphonLogicalReplicationSlotLagHigh runbook](./SiphonLogicalReplicationSlotLagHigh.md)
- [NATS service overview](../../nats/README.md)
