# PatroniRegistryServiceDnsLookupsApdexSLOViolation

## Overview

The latency of the DNS lookups performed by the registry to resolve database replica hosts exceed the configured threshold for a prolonged period of time. This can be due to:

- Missing or unhealthy/unresponsive Consul DNS service;
- General network/DNS issues.

The HTTP API component makes use of database load balancing. Delays in performing these lookups means that the registry won't be able to refresh the replicas pool as soon as possible, which may increase the load on the primary server.

As recipient of this alert, please identify why DNS lookups are taking longer than expected. Resolve the underlying cause for the latency spike. If suspecting of any application-side metrics issues, inform the development team.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `registry_database_lb_lookup_seconds` (histogram). It measure the latency (seconds) of the application-side load balancer replica DNS lookups performed by each registry instance.

The current threshold is based on the p90 latency observed in each environment during the last 7 days ([source](https://dashboards.gitlab.net/goto/h9zDsinNR?orgId=1)). The metric value should remain below the defined threshold.

## Alert Behavior

This is expected to be rare. There are no automated silencing rules. The alert should be silenced if the reported value was found to be incorrect and a related application change is due for deployment soon.

30 days worth of data around enabling load balancing in staging can be observed [here](https://dashboards.gitlab.net/goto/yrH5ymnHg?orgId=1). We faced some network constraints, thus we can see how it looks like when a large latency was observed and after the problem was resolved.

## Severities

The registry is able to operate using an empty replica pool, in which case all queries are directed to primary. Therefore, this alert does not pose any immediate availability risk, but will increase the load on the primary. `s4` is likely the most appropriate severity.

All users may be affected, but only if the primary server becomes overloaded, at which point queries and therefore API requests may suffer increased latency. Ensure the primary is not overloaded. If there is plently of room left, then this is low severity. Otherwise, `s3` is appropriate.

## Verification

- Metrics:
  - [Alerting query](https://dashboards.gitlab.net/goto/ZOuJbc7Hg?orgId=1)
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail)
  - [`consul: Overview`](https://dashboards.gitlab.net/d/consul-main/consul3a-overview)

- Logs: [This query](https://nonprod-log.gitlab.net/app/r/s/s6i9u) shows the error log messages that are emitted when the registry fails to resolve database replicas.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

Before proceding with a rollback, please:

- Check the changelog in the MR that updated the registry.
- Review MRs included in the related release issue
- If any MR has the label `~cannot-rollback` applied, a detailed description should exist in that MR.
- Otherwise, proceed to revert the commit and watch the deployment.
- Review the dashboards and expect the metric to go back to normal.

## Troubleshooting

We need to identify why DNS lookups are taking longer than expected. To do so we can look at the following dashboards and metrics:

1. [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail): This dashboard includes the application metrics that triggered this alarm. Look at the `Load Balancing` panel for more details. The included graphs allow us to identify the current DNS lookup latency (aggregated and broken by SRV/Host lookups) and when the problem started.

2. [`consul: Overview`](https://dashboards.gitlab.net/d/consul-main/consul3a-overview): Look at the Consul metrics to identify any related issues.

## Possible Resolutions

Resolve the underlying cause for the latency spike.

If you suspect of any application-side metrics issues, please inform the development team.

## Dependencies

- PgBouncer
- Patroni
- Consul

## Escalation

Escalate if registry SLIs are breached. Escalate to the development team if metric values appear to be innacurate or further help is required for investigation:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at [registry/registry-db.yml](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml).

## Related Links

- [`ContainerRegistryDBLoadBalancerReplicaPoolSize`](./ContainerRegistryDBLoadBalancerReplicaPoolSize.md) alert;
- [Feature runbook](../db-load-balancing.md);
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md).
