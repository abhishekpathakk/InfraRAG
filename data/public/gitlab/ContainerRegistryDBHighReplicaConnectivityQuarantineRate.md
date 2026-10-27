# ContainerRegistryDBHighReplicaConnectivityQuarantineRate

## Overview

This alert is triggered when replicas are being quarantined due to connectivity issues at a rate exceeding 0.05 quarantines/second for 10 minutes. Replicas are quarantined for connectivity issues when:

- **Consecutive failures**: A replica fails to connect 3 times in a row;
- **Flapping behavior**: A replica is added/removed from the pool 5+ times within 60 seconds.

This indicates network issues, replica instability, or infrastructure problems affecting database connectivity.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `registry_database_lb_pool_events_total` with labels `event="replica_quarantined", reason="connectivity"`. The alert fires when the rate exceeds 0.05/second (~3 quarantines/minute) sustained for 10 minutes.

Quarantined replicas are automatically reintegrated after a 5-minute cooldown period.

## Alert Behavior

This alert indicates active connectivity problems. The quarantine mechanism is protecting the load balancer from repeatedly attempting connections to unstable replicas.

## Severities

- **s3**: Connectivity issues are being mitigated by the quarantine mechanism, but underlying problems need investigation.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - Check `registry_database_lb_pool_events_total{event="replica_quarantined", reason="connectivity"}`
  - Check `registry_database_lb_pool_size` for current pool size

- Logs: Filter by `json.msg: "replica quarantined"` to identify affected replicas and reasons.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. Identify which replicas are being quarantined from logs:
   - [Kibana: replica quarantined (connectivity)](https://log.gprd.gitlab.net/app/r/s/NWYKj)
   - Look for `json.db_host_addr` field to identify the affected replica.
2. Check network connectivity from registry pods to those specific replicas:
   - Test connectivity using `kubectl exec` into a registry pod and attempting to reach the replica.
3. Check PgBouncer status on affected replicas:
   - [Grafana Explore: PgBouncer active connections](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22pgbouncer_pools_server_active_connections%7Benv%3D%5C%22gprd%5C%22,%20type%3D%5C%22patroni-registry%5C%22%7D%22%7D%5D%7D%7D)
4. Check Patroni cluster health for the affected replicas:
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
   - Look for replica lag, connection counts, and cluster membership.
5. Look for any network policy changes or firewall issues.

## Possible Resolutions

- Restore network connectivity to affected replicas;
- Investigate and fix PgBouncer issues on replica hosts;
- Address Patroni cluster member health issues;
- Quarantined replicas will auto-reintegrate after 5 minutes once connectivity is restored.

## Dependencies

- PgBouncer
- Patroni
- Network infrastructure

## Escalation

Escalate if multiple replicas are being quarantined or if pool size drops significantly:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at:

- [registry/registry-db.yml (gprd)](../../../mimir-rules/gitlab-gprd/registry/registry-db.yml)
- [registry/registry-db.yml (gstg)](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml)

## Related Links

- [Feature runbook](../db-load-balancing.md)
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
- [Connectivity tracking MR](https://gitlab.com/gitlab-org/container-registry/-/merge_requests/2596)
