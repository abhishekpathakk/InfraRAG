# ContainerRegistryDBHighReplicaLagQuarantineRate

## Overview

This alert is triggered when replicas are being quarantined due to replication lag exceeding thresholds at a rate of more than 0.05 quarantines/second for 5 minutes. This indicates:

- High write load on the primary database;
- Replica performance issues (slow disk, CPU saturation);
- Replication bottlenecks;
- Network issues affecting WAL streaming.

Replicas with excessive lag are quarantined to prevent stale reads. They are automatically reintegrated once they catch up.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `registry_database_lb_pool_events_total` with labels `event="replica_quarantined", reason="replication_lag"`. The alert fires when the rate exceeds 0.05/second (~3 quarantines/minute) sustained for 5 minutes.

Related metrics:

- `registry_database_lb_lag_bytes` - Replication lag in bytes per replica
- `registry_database_lb_lag_seconds` - Replication lag in seconds per replica

## Alert Behavior

This alert has a shorter duration (5 minutes) and higher threshold (0.05/sec) compared to connectivity quarantine alerts because lag-based quarantines can happen more frequently under load and indicate a more immediate performance concern.

## Severities

- **s3**: Replication lag is being mitigated by the quarantine mechanism, but may indicate primary database overload.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview) - Replication lag graphs
  - Check WAL generation rate on primary

- Logs: Filter by `json.msg: "replica quarantined" AND json.reason: "replication_lag"` to identify affected replicas.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. Check primary database WAL generation rate - is it unusually high?
   - [Grafana Explore: WAL generation rate](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22rate(pg_xlog_position_bytes%7Benv%3D%5C%22gprd%5C%22,%20type%3D%5C%22patroni-registry%5C%22%7D%5B5m%5D)%22%7D%5D%7D%7D)
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview) - WAL panels.
2. Check replica disk I/O and CPU utilization:
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview) - Host metrics panels.
3. Check network throughput between primary and replicas.
4. Look for any long-running transactions or maintenance operations:
   - [Grafana Explore: active transactions](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22pg_stat_activity_count%7Benv%3D%5C%22gprd%5C%22,%20type%3D%5C%22patroni-registry%5C%22,%20state%3D%5C%22active%5C%22%7D%22%7D%5D%7D%7D)
5. Identify which replicas are being quarantined from logs:
   - [Kibana: replica quarantined (replication_lag)](https://log.gprd.gitlab.net/app/r/s/QBFMD)
   - Look for `json.db_host_addr` and `json.lag_bytes` fields.

## Possible Resolutions

- Reduce write load on primary if possible;
- Investigate and resolve replica performance bottlenecks;
- Scale up replica resources if needed;
- Quarantined replicas will auto-reintegrate once they catch up on lag.

## Dependencies

- Patroni (replication)
- Network infrastructure (WAL streaming)

## Escalation

Escalate if lag-based quarantines persist or if primary shows signs of overload:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at:

- [registry/registry-db.yml (gprd)](../../../mimir-rules/gitlab-gprd/registry/registry-db.yml)
- [registry/registry-db.yml (gstg)](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml)

## Related Links

- [Feature runbook](../db-load-balancing.md)
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
- `ContainerRegistryPrimaryDatabaseWALGenerationSaturationSustainedOver150MBS` alert
