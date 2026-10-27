# ContainerRegistryDBReplicaPoolDegraded

## Overview

This alert is triggered when the replica pool size has dropped below 50% of the 1-day average for at least 5 minutes. This indicates a significant reduction in available replicas, which may be caused by:

- Multiple replica failures;
- Widespread network connectivity issues;
- Infrastructure problems affecting multiple hosts;
- Mass quarantining due to connectivity or lag issues.

This is an early warning before the pool becomes completely empty.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert compares `avg(registry_database_lb_pool_size)` to `avg_over_time(avg(registry_database_lb_pool_size)[1d:])`. The alert fires when current pool size is less than 50% of the 1-day average.

This adaptive threshold automatically adjusts if the expected replica count changes.

## Alert Behavior

This alert provides early warning of pool degradation. It fires before the pool is completely empty, giving operators time to investigate and respond.

## Severities

- **s3**: Significant pool degradation increases load on remaining replicas and may impact performance, but the registry remains operational.

If this alert is followed by `ContainerRegistryDBNoReplicasAvailable` (s2), the situation has escalated to critical.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - Check current `registry_database_lb_pool_size` vs historical average
  - Check `registry_database_lb_pool_events_total` for quarantine events

- Logs: Filter by `json.msg: "replica quarantined" or "removing replica"` to identify what's reducing pool size.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. Identify how many replicas are currently available vs expected:
   - [Grafana Explore: pool size](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22registry_database_lb_pool_size%7Benv%3D%5C%22gprd%5C%22%7D%22%7D%5D%7D%7D)
   - [Grafana: registry Database Detail](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel.
2. Check which replicas are missing/quarantined and why:
   - [Kibana: replica quarantined](https://log.gprd.gitlab.net/app/r/s/WpHHK)
   - [Kibana: replica removed](https://log.gprd.gitlab.net/app/r/s/sDBOi)
3. Check Patroni cluster status - are replicas healthy?
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
4. Check network connectivity to replica hosts.
5. Check for any infrastructure incidents affecting multiple hosts.

## Possible Resolutions

- Restore connectivity to unavailable replicas;
- Wait for quarantined replicas to auto-reintegrate (5-minute cooldown);
- Address underlying infrastructure or network issues;
- Scale up if replicas are permanently lost.

## Dependencies

- PgBouncer
- Patroni
- Network infrastructure

## Escalation

Escalate immediately if pool continues to degrade or if remaining replicas show signs of stress:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at:

- [registry/registry-db.yml (gprd)](../../../mimir-rules/gitlab-gprd/registry/registry-db.yml)
- [registry/registry-db.yml (gstg)](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml)

## Related Links

- [Feature runbook](../db-load-balancing.md)
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
- [`ContainerRegistryDBNoReplicasAvailable`](./ContainerRegistryDBNoReplicasAvailable.md) alert (escalation)
