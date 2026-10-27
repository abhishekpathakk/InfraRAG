# ContainerRegistryDBNoReplicasAvailable

## Overview

This alert is triggered when the replica pool size has been zero for at least 2 minutes. This is a **critical** condition meaning:

- All database replicas are unavailable, unreachable, or quarantined;
- **All read queries are being routed to the primary database**;
- Primary database load is significantly increased.

Immediate investigation is required.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `avg(registry_database_lb_pool_size) == 0`. The alert fires after the pool has been empty for 2 minutes.

## Alert Behavior

This is the most severe replica pool alert. It indicates complete loss of read replica capacity. The registry will continue to function by routing all queries to the primary, but this significantly increases primary load and may lead to performance degradation.

## Severities

- **s2**: Critical condition. All read traffic is hitting the primary database, which may become overloaded.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - Check `registry_database_lb_pool_size` - should be 0
  - Check primary database load metrics
  - Check `registry_database_lb_pool_events_total` for recent quarantine events

- Logs:
  - Filter by `json.msg: "replica quarantined"` to see why replicas were removed
  - Filter by `json.msg: "no replicas available"` to confirm fallback to primary

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. **Immediate**: Check primary database health and load - is it coping?
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview) - Primary load panels.
   - [Grafana Explore: primary connections](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22pg_stat_activity_count%7Benv%3D%5C%22gprd%5C%22,%20type%3D%5C%22patroni-registry%5C%22%7D%22%7D%5D%7D%7D)
2. Check Patroni cluster status - are replicas up?
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview) - Cluster membership panel.
3. Check network connectivity from registry pods to all replica hosts.
4. Check PgBouncer status on replica hosts:
   - [Grafana Explore: PgBouncer connections](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22pgbouncer_pools_server_active_connections%7Benv%3D%5C%22gprd%5C%22,%20type%3D%5C%22patroni-registry%5C%22%7D%22%7D%5D%7D%7D)
5. Review recent events - what caused all replicas to become unavailable?
   - [Kibana: replica quarantined](https://log.gprd.gitlab.net/app/r/s/WpHHK)
   - [Kibana: no replicas available](https://log.gprd.gitlab.net/app/r/s/kJSgR)
6. Check if replicas are quarantined (they will auto-reintegrate after 5 minutes).

## Possible Resolutions

- Restore network connectivity to replicas;
- Fix PgBouncer issues on replica hosts;
- Address Patroni cluster problems;
- Wait for quarantined replicas to auto-reintegrate (5-minute cooldown);
- If replicas are permanently lost, scale up or failover.

## Dependencies

- PgBouncer
- Patroni
- Consul
- Network infrastructure

## Escalation

**Escalate immediately** - this is an s2 condition:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)
- Consider paging database on-call if primary shows signs of overload.

## Definitions

The definition for this alert can be found at:

- [registry/registry-db.yml (gprd)](../../../mimir-rules/gitlab-gprd/registry/registry-db.yml)
- [registry/registry-db.yml (gstg)](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml)

## Related Links

- [Feature runbook](../db-load-balancing.md)
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
- [`ContainerRegistryDBReplicaPoolDegraded`](./ContainerRegistryDBReplicaPoolDegraded.md) alert (early warning)
- [`ContainerRegistryDBLoadBalancerReplicaPoolSize`](./ContainerRegistryDBLoadBalancerReplicaPoolSize.md) alert (related)
