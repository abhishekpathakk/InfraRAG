# High Number of Overdue Online GC Tasks

## Background

The new version of the Container Registry includes an [online Garbage Collection (GC)](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs-gitlab/db/online-garbage-collection.md) feature that takes care of deleting dangling artifacts both from the storage backend and the database. Artifacts can be of two types, blobs or manifests.

Online GC is composed by a pair of background processes (workers) in every registry instance, one for each artifact type. Workers operate on top of the metadata database, using two dedicated database tables as queues for tasks (one for each artifact type). Tasks are queued in response to API requests and processed by workers. Every task has a `review_after` attribute which defines the timestamp after which it can be picked for review by a worker. An "overdue" task is one whose `review_after` is less than the current time.

For more details about how online GC works, please see the linked documentation.

⚠️ The container registry online GC feature is still in the early days. It is expected that we will need to perform additional debugging and scaling/performance adjustments during the [GitLab.com gradual rollout](https://gitlab.com/groups/gitlab-org/-/epics/6442), so a good portion of alerts may be a false alarm.

## Causes

A high number of overdue tasks sitting on the queues is likely related to one of the following possibilities:

1. A problem establishing connections to the database or executing queries;
1. A problem establishing connections to the storage backend;
1. An application bug is leading to processing failures.

## Symptoms

The [`ContainerRegistryGCOverdue[Blob|Manifest]QueueTooLarge`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/legacy-prometheus-rules/registry-db.yml) alerts (one for each artifact type) will be triggered if the number of overdue tasks remains above the configured threshold for longer than the configured period.

No API impact is expected in these situations, as online GC is a background process and therefore detached from the main (server) process.

## Troubleshooting

We first need to identify the cause for the accumulation of overdue tasks. For this, we can look at the following Grafana dashboards:

1. [`registry-main/registry-overview`](https://dashboards.gitlab.net/d/registry-main/registry-overview)
1. [`registry-database/registry-database-detail`](https://dashboards.gitlab.net/d/registry-database/registry-database-detail)
1. [`registry-app/registry-application-detail`](https://dashboards.gitlab.net/d/registry-app/registry-application-detail)
1. [`registry-gc/registry-garbage-collection-detail`](https://dashboards.gitlab.net/d/registry-gc/registry-garbage-collection-detail)

In (1), we should inspect the current Apdex/error rate SLIs, both for the server (to rule out any unexpected customer impact) and database components. For the database component, we can expand the `database Service Level Indicator Detail` row to observe the latency and rate for every single query executed against the database (a unique name identifies them). If the problem is limited to a subset of slow queries, we should identify them here. Queries related to online GC are prefixed with `gc_`, making them easy to identify.

In (2), we should double-check the connection pool saturation graph. Online GC workers need to connect with the database. Therefore a prolonged saturation can lead to this problem. See the [related runbook](./app-db-conn-pool-saturation.md) for additional leads.

In (3), we should look for potential exhaustions in CPU and memory across pods.

Finally and most importantly, in (4), we can look at all online GC metrics. Here we can see the number and the evolution of all queued tasks, including the overdue ones. Try to identify the point in time where the significant increase started and link it to the remaining metrics. In this same dashboard, it's also possible to observe database and storage backend metrics, so a problem in operating each of those backends can be detected here. Run rates and latencies are also displayed.

In the presence of errors, we should also look at the registry access/application logs in Kibana. This should allow us to identify the cause of application/database/storage/network errors. The same applies to Sentry, where all unknown application errors are reported.

## Resolution

Suppose there are no signs of relevant application/database/network errors, and all metrics seem to point to an inability to keep up with the demand. In that case, we should likely adjust the [online GC settings](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/configuration.md#gc) to meet the demand by, for example, reducing the time between reviews.

In the presence of errors, the development team should be involved in debugging the underlying cause.
