# Pulp SLIs

Pulp uses Service Level Indicators (SLIs) to monitor the health and performance of its components. These SLIs are defined in the [metrics catalog](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet) and are used to measure availability and latency for the service.

## Overview

The Pulp service has the following SLIs:

| SLI | Description | Type |
| --- | ----------- | ---- |
| `pulp_app_api` | Pulp application API service requests | Apdex + Error Rate |
| `pulp_app_content` | Pulp application content API requests | Apdex + Error Rate |
| `pulp_nginx` | Nginx ingress controller load balancer requests | Apdex + Error Rate |
| `pulp_cloudsql` | GCP CloudSQL PostgreSQL database operations | Apdex + Request Rate |
| `pulp_gcs` | GCS bucket storage operations | Request Rate |
| `pulp_redis` | GCP Redis Memorystore caching operations | Request Rate |

## Observability

The SLIs appear in the [Pulp Overview dashboard](https://dashboards.gitlab.net/d/pulp-main/pulp-overview).

## CloudSQL and Memorystore

The Pulp Overview dashboard includes two collapsed rows: `CloudSQL` and
`Memorystore`. The `CloudSQL` row shows performance, connection, disk,
network, and tuple panels. The `Memorystore` row shows client, workload,
and data panels.

To find out if CloudSQL is slow, open the `CloudSQL` row. The first panels
show the query latency, the query, IO, and lock time from Query Insights,
CPU and memory utilization, the data cache hit ratio, temporary bytes,
deadlocks, disk throughput, and transactions.

The Stackdriver exporters label these metrics `type="pulp"`.
gitlab-com/gl-infra/argocd/apps!4039 and gitlab-com/gl-infra/argocd/apps!4053
add the relabel rules. gitlab-com/gl-infra/argocd/apps!4052 adds the ops
metric allowlists.

The saturation rules track six components: `cloudsql_cpu`, `cloudsql_disk`,
`cloudsql_memory`, `memorystore_redis_cpu`, `memorystore_redis_memory`, and
`memorystore_system_memory`.

## Application SLIs

### pulp_app_api

The `pulp_app_api` SLI monitors the Pulp API service, which handles administrative operations such as repository management, content synchronization, and user management.

**Metrics:**

- [`api_request_duration_milliseconds_bucket`](https://dashboards.gitlab.net/goto/cfccxbl51xon4c?orgId=1) - Request latency histogram
- [`api_request_duration_milliseconds_count`](https://dashboards.gitlab.net/goto/dfccxj4heohdsb?orgId=1) - Total request count

**[Apdex Thresholds:](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet#L178-179)**

- [Satisfied: <= 2s](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet#L179)
- [Tolerated: <= 10s](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet#L178)

**Significant Labels:**

- `http_method` - HTTP request method (GET, POST, PUT, DELETE, etc.)
- `http_target` - API endpoint path
- `http_status_code` - HTTP response status code

**Error Rate:**
Tracks 5xx HTTP status codes as errors.

### pulp_app_content

The `pulp_app_content` SLI monitors the Pulp Content API service, which handles package downloads and content delivery to clients (e.g., yum/dnf clients fetching packages).

**Metrics:**

- [`content_request_duration_milliseconds_bucket`](https://dashboards.gitlab.net/goto/ffccxv4kr1ipsa?orgId=1) - Request latency histogram
- [`content_request_duration_milliseconds_count`](https://dashboards.gitlab.net/goto/ffccxx11rzncwe?orgId=1) - Total request count

**Apdex Thresholds:**

- [Satisfied: <= 10s](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet#L205)

**Significant Labels:**

- `http_method` - HTTP request method
- `http_route` - Content API route
- `http_status_code` - HTTP response status code

**Error Rate:**
Tracks 5xx HTTP status codes as errors.

## Other Metrics

In addition to the SLIs above, the following metrics are available in the [Pulp Overview dashboard](https://dashboards.gitlab.net/d/pulp-main/pulp-overview).

### Task Queue Metrics

#### Longest Unblocked Task Wait Time

Tracks how long the oldest unblocked task has been waiting in the queue. Lower values are better.

**Metric:**

- [`tasks_longest_unblocked_time_seconds{namespace="pulp"}`](https://dashboards.gitlab.net/goto/bfccx1nvhwetca?orgId=1)

#### Unblocked Task Queue Length

Tracks the number of unblocked tasks waiting to be processed. Lower values are better.

**Metric:**

- [`tasks_unblocked_queue{namespace="pulp"}`](https://dashboards.gitlab.net/goto/bfccx6bt15i4gc?orgId=1)

## Infrastructure SLIs

### pulp_nginx

Monitors the nginx ingress controller that load balances traffic to Pulp services.

**Metrics:**

- [`nginx_ingress_controller_request_duration_seconds_bucket`](https://dashboards.gitlab.net/goto/afccxyedqgydcb?orgId=1) - Request latency histogram
- [`nginx_ingress_controller_requests`](https://dashboards.gitlab.net/goto/afccxz69rhh4wc?orgId=1) - Total request count

**Apdex Threshold:**

- [Satisfied: <= 10s](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet#L88)

**Significant Labels:**

- `method` - HTTP method
- `path` - Request path
- `status` - HTTP status code

### pulp_cloudsql

Monitors the GCP CloudSQL PostgreSQL instance used by Pulp.

**Metrics:**

- [`stackdriver_cloudsql_database_cloudsql_googleapis_com_database_postgresql_statements_executed_count`](https://dashboards.gitlab.net/goto/dfccye4sgllhce?orgId=1)
  (request rate)
- `stackdriver_cloudsql_instance_database_cloudsql_googleapis_com_database_postgresql_insights_aggregate_latencies_bucket`
  (apdex, from Query Insights, in microseconds)

**Apdex:** a query is satisfied if it takes less than 1 s
(the 1048576 microsecond bucket, stored as `le="1.048576e+06"`). A
database query that takes longer than 1 s is slow. The SLO alert fires
when more than 0.1% of the queries are slow, for example because of CPU,
IO, or lock problems. It does not fire for one slow query.

**Significant Labels:**

- `database_id` - Cloud SQL database identifier
- `database` - Database name
- `operation_type` - Type of SQL operation

### pulp_gcs

Monitors the GCS bucket used for package storage.

**Metrics:**

- [`stackdriver_gcs_bucket_storage_googleapis_com_api_request_count`](https://dashboards.gitlab.net/goto/afccybtvirhmod?orgId=1)

**Significant Labels:**

- `bucket_name` - GCS bucket name
- `method` - API method

### pulp_redis

Monitors the GCP Redis Memorystore instance used for caching and session management.

**Metrics:**

- [`stackdriver_redis_instance_redis_googleapis_com_commands_calls`](https://dashboards.gitlab.net/goto/bfccym3wv9b7ke?orgId=1)

**Significant Labels:**

- `instance_id` - Redis instance identifier

## Related Documentation

- [Pulp Troubleshooting](./troubleshooting.md)
- [Logs](./README.md#logging)
- [Pulp Functional Operations](./functional-operations.md)
- [Pulp Infrastructure Setup](./infrastructure-setup.md)
- [Pulp Backup & Restore](./backup-restore.md)
- [Infrastructure Architecture](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp/-/blob/main/ARCHITECTURE.md)
- [Metrics Catalog Definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/pulp.jsonnet)
