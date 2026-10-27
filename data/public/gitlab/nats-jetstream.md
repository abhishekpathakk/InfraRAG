# Orbit NATS JetStream SLO alerts

Covers `OrbitServiceNatsJetstreamErrorSLOViolation`, `OrbitServiceNatsJetstreamTrafficCessation`
and `OrbitServiceNatsJetstreamTrafficAbsent`.

## Overview

JetStream is the persistence layer on the NATS cluster: it stores the indexing job
streams and the KV buckets (locks, indexing progress).

These alerts cover only the NATS that runs in the Orbit clusters (orbit-prd, orbit-stg) for
Orbit and Siphon. Other NATS deployments belong to the `nats` service. These alerts are
severity s3, do not page and post to `#f_orbit_alerts`.

## Services

- [Orbit service overview](../README.md)
- [NATS runbook](../../nats/README.md)
- Owner team: `context_systems`, for the NATS in the Orbit clusters and the Orbit
  consumers. Siphon, the other producer, is owned by `platform_insights`.

## Alerts

### OrbitServiceNatsJetstreamErrorSLOViolation

Message redeliveries are rising. A redelivery means a consumer took a message but did
not acknowledge it in time, so JetStream handed it out again. This is how indexer
failures self-heal, but a rising rate means work is failing repeatedly.

### OrbitServiceNatsJetstreamTrafficCessation / TrafficAbsent

No JetStream messages are moving. `TrafficCessation` means traffic recently dropped to
zero, `TrafficAbsent` means it has been missing for longer.

## Metrics

The `nats_jetstream` SLI in
[`metrics-catalog/services/orbit.jsonnet`](../../../metrics-catalog/services/orbit.jsonnet)
uses JetStream stream and consumer metrics (total messages, redeliveries) from the
Prometheus exporter.

A low background redelivery rate is normal during deploys and pod restarts. Sustained
growth is not.

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D)
  filtered on the alertname.
- Redeliveries spike during indexer rollouts (in-flight messages get redelivered). A
  spike that lines up with a deploy and settles within minutes is expected.

## Severities

- s3, no paging. User impact is indexing delay. A redelivery loop on one subject can
  also starve other work on the same consumer.

## Verification

The alerts fire on these recording rules in the `mimir-analytics-eventsdot` datasource
([Grafana Explore](https://dashboards.gitlab.net/explore)):

```promql
# Error ratio
gitlab_component_errors:ratio_1h{type="orbit", component="nats_jetstream", monitor="global"}

# Request rate (traffic cessation fires when this drops to zero)
gitlab_component_ops:rate_1h{type="orbit", component="nats_jetstream", monitor="global"}
```

- [NATS dashboard](https://dashboards.gitlab.net/d/orbit-orbit-nats), JetStream panels:
  redeliveries, ack pending, consumer lag.
- Per-stream and per-consumer state from nats-box:
  [Check NATS stream health](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/code_indexing.md#check-nats-stream-health).
- Cross-check which handler is failing on the
  [indexer dashboard](https://dashboards.gitlab.net/d/orbit-orbit-gkg-indexer); redeliveries
  are the flip side of handler errors.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged)
  for services `nats` and `gkg`. Stream, consumer or subject config changes are the
  usual suspects.
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Redeliveries concentrated on one subject | Poison message: a task that fails on every attempt | Find the failing handler in the logs, then [purge the subject](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/sdlc_indexing.md#purge-a-specific-subject) or wait for dead-lettering (code tasks) |
| Redeliveries across all subjects | Consumers too slow: ClickHouse insert latency or undersized pools | Check ClickHouse first, then scale the indexer pools |
| Consumer stopped consuming after a config change | JetStream does not apply config changes to existing streams or buckets in place | Delete the stream or KV bucket and restart the pod so Orbit recreates it ([Common signatures](../README.md#common-signatures)) |
| Ack pending grows, disk follows | Consumers lagging, persisted messages accumulate | Scale indexers; disk has its own paging alert (`nats_disk_space`) with runbook [docs/nats/operations.md](../../nats/operations.md) |

Dead letter queue procedures (inspect, replay, purge) are in the KG repo's
[code indexing runbook](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/code_indexing.md#dead-letter-queue).

## Possible Resolutions

- Remove or dead-letter the poison message, then replay once the cause is fixed.
- Scale the consuming pool or relieve ClickHouse pressure
  ([Pause and resume indexing](../README.md#pause-and-resume-indexing)).

## Dependencies

- Consumers: indexer pools. Producers: dispatcher, Siphon. Storage: JetStream file
  storage on the NATS PVCs, backed up by the Velero schedule `velero-nats-backup`.

## Escalation

- Ask in `#f_orbit_dev` (team channel for `context_systems`). For Siphon producer
  problems, ask in `#g_analytics_platform_insights`.
- Generic SLO playbooks: [ErrorSLOViolation](../../alerts/ErrorSLOViolation.md),
  [TrafficAbsent](../../alerts/TrafficAbsent.md).

## Definitions

- [Alert rules](../../../mimir-rules/analytics-eventsdot/orbit/autogenerated-analytics-eventsdot-orbit-service-level-alerts.yml)
  (generated, do not edit).
- [Tune the SLI](../../../metrics-catalog/services/orbit.jsonnet), then run `make generate`.

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
