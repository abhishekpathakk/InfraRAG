# Orbit dispatcher SLO alerts

Covers `OrbitServiceGkgDispatcherErrorSLOViolation`, `OrbitServiceGkgDispatcherTrafficCessation`
and `OrbitServiceGkgDispatcherTrafficAbsent`.

## Overview

The dispatcher is a singleton. It runs graph schema migrations and periodic tasks, reads
the datalake ClickHouse and Siphon CDC events, and publishes indexing jobs to NATS.

No user-facing errors: queries keep working, data goes stale. These alerts are severity
s3 and do not page. They post to `#f_orbit_alerts`.

## Services

- [Orbit service overview](../README.md)
- Owner team: `context_systems`

## Alerts

### OrbitServiceGkgDispatcherErrorSLOViolation

Scheduler task runs are ending with `outcome="error"`.

### OrbitServiceGkgDispatcherTrafficCessation / TrafficAbsent

No scheduler tasks are running. Since the dispatcher is the only source of indexing
jobs, all indexing dries up downstream. `TrafficCessation` means task runs recently
dropped to zero, `TrafficAbsent` means they have been missing for longer.

## Metrics

The `gkg_dispatcher` SLI in
[`metrics-catalog/services/orbit.jsonnet`](../../../metrics-catalog/services/orbit.jsonnet)
counts `gkg_scheduler_task_runs_total`, errors are runs with `outcome="error"`.

## Alert Behavior

- Silence via [Alertmanager](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22orbit%22%7D)
  filtered on the alertname.
- Every deploy causes a short traffic gap: the dispatcher uses the `Recreate` strategy,
  so there is no overlap between old and new pod. A cessation alert right after a merge
  to argocd-apps is usually just that.

## Severities

- s3, no paging. User impact is data freshness lag, growing with time. In-flight jobs on
  NATS keep draining, so the effect is delayed.

## Verification

The alerts fire on these recording rules in the `mimir-analytics-eventsdot` datasource
([Grafana Explore](https://dashboards.gitlab.net/explore)):

```promql
# Error ratio
gitlab_component_errors:ratio_1h{type="orbit", component="gkg_dispatcher", monitor="global"}

# Request rate (traffic cessation fires when this drops to zero)
gitlab_component_ops:rate_1h{type="orbit", component="gkg_dispatcher", monitor="global"}
```

- [Orbit Overview dashboard](https://dashboards.gitlab.net/d/orbit-main/orbit3a-overview?orgId=1&var-environment=orbit-prd),
  `gkg_dispatcher` row: task run rate and error rate.
- Pod state: `kubectl --context gke_gl-orbit-prd_us-east1_orbit-prd -n gkg get deploy/gkg-dispatcher`.
- Logs: [Kibana, orbit index](https://log.gprd.gitlab.net/app/r/s/DhOL5), filter
  `json.mode: dispatch-indexing`. Task outcomes are logged per run.

## Recent changes

- [argocd-apps MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged)
  touching `services/gkg`. Schema-version bumps matter most here, see
  [Service Changes](../README.md#service-changes).
- [Production issues labeled Service::Orbit](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AOrbit).

## Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| Readiness 503 right after a deploy | A schema migration is running, or the migration lock is held | Wait for the migration, then check dispatcher logs. Migration locks live in the NATS KV bucket `indexing_locks` |
| Task errors reading the datalake | Datalake ClickHouse slow or unreachable, or Siphon CDC behind | Check the [Siphon dashboard](https://dashboards.gitlab.net/d/orbit-orbit-siphon) and datalake health |
| Fails to start after a stream or KV config change | JetStream does not apply config changes to existing streams or buckets in place | Delete the stream or KV bucket, restart the pod so Orbit recreates it ([Common signatures](../README.md#common-signatures)) |
| `get_graph_status` logs `KV bucket ... not registered` | KV bucket not created at startup | Cosmetic, do not roll back for this alone |
| OOM | Unoptimized query execution in a periodic task | More memory as a stopgap, report to `context_systems` |

Scheduler cadence locks (one dispatcher replica runs each task) are also in the
`indexing_locks` KV bucket, inspect with
[nats-box](https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/blob/main/docs/dev/runbooks/server_configuration.md#troubleshoot-nats-with-nats-box).

## Possible Resolutions

- Deploy-related gap: none needed, the replacement pod picks up.
- Stuck migration or lock: check dispatcher logs, inspect and if necessary clear the lock
  in the `indexing_locks` KV bucket, restart the pod.
- Rollback across a `SCHEMA_VERSION` is a manual operation, see
  [Recent changes and rollback](../README.md#recent-changes-and-rollback).

## Dependencies

- Datalake ClickHouse and Siphon CDC (job sources), NATS JetStream (job sink and locks).
  The dispatcher cannot scale past 1 replica.

## Escalation

- Ask in `#f_orbit_dev` (team channel for `context_systems`).
- Generic SLO playbooks: [ErrorSLOViolation](../../alerts/ErrorSLOViolation.md),
  [TrafficAbsent](../../alerts/TrafficAbsent.md).

## Definitions

- [Alert rules](../../../mimir-rules/analytics-eventsdot/orbit/autogenerated-analytics-eventsdot-orbit-service-level-alerts.yml)
  (generated, do not edit).
- [Tune the SLI](../../../metrics-catalog/services/orbit.jsonnet), then run `make generate`.

## Related Links

- [Related alerts](./)
- [Orbit runbook](../README.md)
