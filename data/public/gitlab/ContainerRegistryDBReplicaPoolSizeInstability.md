# ContainerRegistryDBReplicaPoolSizeInstability

## Overview

This alert is triggered when the replica pool size has been fluctuating significantly (standard deviation > 1) over a 15-minute window for at least 5 minutes. This indicates:

- Replicas frequently joining and leaving the pool;
- Intermittent connectivity or health check failures;
- Infrastructure instability affecting multiple replicas.

A stable pool should have near-zero standard deviation.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `stddev_over_time(registry_database_lb_pool_size[15m])`. The alert fires when the standard deviation exceeds 1 for 5 minutes.

For context:

- A stddev of 0 means the pool size is completely stable
- A stddev of 1 means the pool size is fluctuating by roughly ±1 replica
- Higher values indicate more severe fluctuations

## Alert Behavior

This alert complements the churn rate alert by detecting pool size instability regardless of the specific events causing it. It can catch scenarios where replicas are being added and removed in ways not captured by other alerts.

## Severities

- **s3**: Pool instability indicates underlying infrastructure issues but the registry can continue operating.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - Check `registry_database_lb_pool_size` over time to visualize fluctuations
  - Check `registry_database_lb_pool_events_total` for add/remove/quarantine events

- Logs: Filter by `json.msg: "replica"` to see all replica-related events.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. Check which replicas are fluctuating in/out of the pool from logs:
   - [Kibana: replica quarantined](https://log.gprd.gitlab.net/app/r/s/WpHHK)
   - [Kibana: replica added](https://log.gprd.gitlab.net/app/r/s/1c8m3)
   - [Kibana: replica removed](https://log.gprd.gitlab.net/app/r/s/sDBOi)
   - Look for `json.db_host_addr` field to identify which replicas are affected.
2. Investigate if fluctuations correlate with specific events (deployments, network changes).
3. Check for patterns - are the same replicas repeatedly affected?
4. Review Patroni cluster health and membership:
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
5. Check for DNS or service discovery issues:
   - Verify Consul DNS is returning consistent results for `replica.patroni-registry.service.consul`.

## Possible Resolutions

- Identify and fix the root cause of replica instability;
- Address network or connectivity issues;
- Resolve Patroni cluster health problems.

## Dependencies

- Patroni
- DNS/Consul
- Network infrastructure

## Escalation

Escalate if instability persists or worsens:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at:

- [registry/registry-db.yml (gprd)](../../../mimir-rules/gitlab-gprd/registry/registry-db.yml)
- [registry/registry-db.yml (gstg)](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml)

## Related Links

- [Feature runbook](../db-load-balancing.md)
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
- [`ContainerRegistryDBHighReplicaPoolChurnRate`](./ContainerRegistryDBHighReplicaPoolChurnRate.md) alert
