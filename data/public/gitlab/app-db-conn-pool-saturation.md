# Database Connection Pool Saturation

Each registry instance (Go application) maintains a configurable application-side connection pool for the underlying PostgreSQL database (through PgBouncer).

⚠️ The container registry database is still in the early days. It is expected that we will need to perform additional debugging and scaling/performance adjustments during the [GitLab.com gradual rollout](https://gitlab.com/groups/gitlab-org/-/epics/6442), so a good portion of alerts may be a false alarm.

## Causes

An application-side connection pool saturation might happen in the following occasions:

1. Configured pool size is not enough to meet the API demand;
1. An unusual delay on establishing connections or executing queries;
1. An application bug is leading to a connection leak (connections not released properly after processing requests).

## Symptoms

The [`ContainerRegistryDBConnPoolSaturationTooHigh`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/legacy-prometheus-rules/registry-db.yml) alert will be triggered if the connection pool saturation remains above the configured threshold for longer than the configured period. If the saturation approaches 100%, this alert will likely be followed by API SLI alerts due to slow or error API responses.

## Troubleshooting

We first need to identify the cause for the saturation. For this, we can look at the following Grafana dashboards:

1. [`registry-main/registry-overview`](https://dashboards.gitlab.net/d/registry-main/registry-overview)
1. [`registry-database/registry-database-detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail)
1. [`registry-app/registry-application-detail`](https://dashboards.gitlab.net/d/registry-app/registry-application-detail)

In (1), we should inspect the current Apdex/error rate SLIs, both for the server (to identify customer impact) and database components. It's also essential to look at the API request rate to rule out any unexpected surge/potential abuse. For the database component, we can expand the `database Service Level Indicator Detail` row to observe the latency and rate for every single query executed against the database (a unique name identifies them). If the problem is limited to a subset of slow queries, we should identify them here.

In (2), we should double-check the connection pool saturation graph. There is a graph for the aggregated saturation another for the per-pod saturation. If the problem is limited to a subset of pods, we should identify them here. Additionally, we have a series of other connection pool metrics/graphs in this dashboard, such as the number of open/in-use/idle connections. Each graph has a helpful explanation of the underlying metric. In the case of a connection pool saturation, we can observe an increase in the `Wait Time` metric displayed in this dashboard. This represents the amount of time that a process had to wait for a database connection. A value above zero will always translate to additional latency for API requests.

In (3), we should look for potential exhaustions in CPU and memory across pods.

In the presence of errors, we should also look at the registry access/application logs in Kibana. This should allow us to identify the cause of application/database/network errors. The same applies to Sentry, where all unknown application errors are reported.

## Resolution

Suppose there are no signs of unexpected surge/potential abuse in request rates, no relevant application/database/network errors, and all metrics seem to point to an inability to keep up with the demand. In that case, we should likely adjust the [connection pool settings](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/configuration.md#pool) to meet the demand.

In the presence of errors, the development team should be involved in debugging the underlying cause.
