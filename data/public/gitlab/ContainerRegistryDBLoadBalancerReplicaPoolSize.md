# ContainerRegistryDBLoadBalancerReplicaPoolSize

## Overview

This alert is triggered when the size of the application-side database load balancer replica pool has been below the configured minimum threshold for a prolongued period of time. This can be due to:

- Missing or unhealthy/unresponsive database replicas hosts;
- Application unable to connect to database replicas hosts due to e.g. a network issue.

The HTTP API component makes use of database load balancing. The registry is able to operate using an empty replica pool, in which case all queries are directed to primary. Therefore, this alert does not pose any immediate availability risk, but will increase the load on the primary.

As recipient of this alert, please confirm if there are missing/unresponsive database replicas hosts and investigate why. Ultimately, restore the number of available replicas.

## Services

- [`registry: Overview`](https://dashboards.gitlab.net/d/registry-main/registry3a-overview)
- [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
- Ownership: [Package:Container Registry](https://handbook.gitlab.com/handbook/engineering/devops/package/)

## Metrics

This alert is based on `registry_database_lb_pool_size`, which is a gauge. It measure the size (count) of the application-side load balancer replica pool reported by each registry instance. The alert observes the maximum of the reported size across all registry instances to exclude temporary fluctuations due to expects events such as scaling.

The current threshold is based on the minimum expected number of replica hosts in each environment. The metric value should equal the minimum expected number of replica hosts in each environment.

## Alert Behavior

This alert is expected to be rare. There are no automated silencing rules. The alert should be silenced if the reported value was found to be incorrect and a related application change is due for deployment soon.

30 days worth of data around enabling load balancing in staging can be observed [here](https://dashboards.gitlab.net/goto/tTp1Bi7HR?orgId=1). We faced some network constraints, thus we can see how it looks like when there were no replicas in the pool and then when the pool was filled with the expected number of replicas.

## Severities

The registry is able to operate using an empty replica pool, in which case all queries are directed to primary. Therefore, this alert does not pose any immediate availability risk, but will increase the load on the primary.

All clients may be affected by this, but only if the primary server becomes overloaded as a side-effect, at which point queries and therefore API requests may suffer increased latency.

Please ensure the primary is not overloaded due to the missing replicas. If there is plently of room left, then this is low severity, likely `s4`. Otherwise, `s3` is appropriate.

## Verification

- Metrics:
  - [Alerting query](https://dashboards.gitlab.net/goto/3y4qfmnHg?orgId=1)
  - [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail)
  - [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview)
  - [`pgbouncer-registry: Overview`](https://dashboards.gitlab.net/d/pgbouncer-registry-main/pgbouncer-registry3a-overview)

- Logs: [This query](https://nonprod-log.gitlab.net/app/r/s/s6i9u) shows the error log messages that are emitted when the registry fails to connect to database replicas.

## Recent changes

Recent registry deployments and configuration changes can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=opened&label_name[]=Service%3A%3AContainer%20Registry).

Before proceding with a rollback, please:

- Check the changelog in the MR that updated the registry.
- Review MRs included in the related release issue
- If any MR has the label `~cannot-rollback` applied, a detailed description should exist in that MR.
- Otherwise, proceed to revert the commit and watch the deployment.
- Review the dashboards and expect the metric to go back to normal.

## Troubleshooting

We need to identify why replica(s) are unhealthy. To do so we can look at the following dashboards and metrics:

1. [`registry: Database Detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail): This dashboard includes the application metrics that triggered this alarm. Look at the `Load Balancing` panel for more details. The included graphs allow us to identify the current pool size and when the problem started.

2. [`patroni-registry: Overview`](https://dashboards.gitlab.net/d/patroni-registry-main/patroni-registry3a-overview): Look at each node metrics to identify which ones are unhealthy and why.
3. [`pgbouncer-registry: Overview`](https://dashboards.gitlab.net/d/pgbouncer-registry-main/pgbouncer-registry3a-overview): Look at the PgBouncer metrics to identify potential issues at the connection pool level.

## Possible Resolutions

Resolve the underlying cause for the unhealthy state of replica(s).

If you suspect of any application-side metrics issues, please inform the development team.

## Dependencies

- PgBouncer
- Patroni
- Consul

## Escalation

Escalate if primary server becomes overloaded due to the missing replicas. Escalate to the development team if metric values appear to be innacurate or further help is required for investigation:

- [`g_container_registry`](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [`s_package`](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)

## Definitions

The definition for this alert can be found at [registry/registry-db.yml](../../../mimir-rules/gitlab-gstg/registry/registry-db.yml).

## Related Links

- [`PatroniRegistryServiceDnsLookupsApdexSLOViolation`](./PatroniRegistryServiceDnsLookupsApdexSLOViolation.md) alert;
- [Feature runbook](../db-load-balancing.md);
- [Feature technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md).
