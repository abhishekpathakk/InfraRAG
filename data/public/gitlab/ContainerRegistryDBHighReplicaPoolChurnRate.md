# ContainerRegistryDBHighReplicaPoolChurnRate

## Overview

This alert is triggered when the database load balancer is experiencing sustained replica DNS changes (additions and removals) at a rate exceeding 0.1 events/second for 15 minutes. This can indicate:

- DNS instability or misconfiguration;
- Network issues causing intermittent connectivity;
- Service discovery problems;
- Infrastructure instability affecting replica hosts.

The registry is able to operate during DNS churn, but frequent replica changes can lead to connection overhead and potential latency increases.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `registry_database_lb_pool_events_total` with labels `event="replica_added", reason="discovered"` and `event="replica_removed", reason="removed_from_dns"`. The alert fires when the combined rate of these events exceeds 0.1/second (~6 events/minute) sustained for 15 minutes.

Note: Brief spikes during deployments are expected and the 15-minute duration helps filter these out.

## Alert Behavior

This alert should be rare under normal operations. The 15-minute duration window is designed to ignore transient spikes from expected events like deployments or scaling operations.

## Severities

- **s3**: This alert indicates infrastructure instability but does not pose immediate availability risk.

## Verification

- Metrics:
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail) - Load Balancing panel
  - Check the `registry_database_lb_pool_events_total` metric for add/remove patterns

- Logs: Filter by `json.msg: "replica is new" or "removing replica"` to see replica pool changes.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

## Troubleshooting

1. Identify replica add/remove events from logs:
   - [Kibana: replica added](https://log.gprd.gitlab.net/app/r/s/1c8m3)
   - [Kibana: replica removed](https://log.gprd.gitlab.net/app/r/s/sDBOi)
   - Look for `json.db_host_addr` field to identify which replicas are churning.
2. Check DNS resolution for the replica hosts - are records stable?
   - Verify Consul DNS is returning consistent results for `replica.patroni-registry.service.consul`.
3. Check network connectivity between registry pods and replica hosts.
4. Look at Patroni cluster status for any failovers or membership changes:
   - [Grafana: patroni-registry Overview](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
5. Review recent infrastructure changes that might affect DNS or networking.

## Possible Resolutions

- Investigate and resolve DNS instability;
- Fix network connectivity issues;
- Address any Patroni cluster instability.

## Dependencies

- DNS (Consul)
- Patroni
- Network infrastructure

## Escalation

Escalate if the churn rate continues to increase or if it starts affecting API latency:

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
