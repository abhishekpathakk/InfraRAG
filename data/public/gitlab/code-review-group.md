# Create:Code Review Group Runbook

## About us

- **Handbook**: [Create:Code Review Group](https://handbook.gitlab.com/handbook/engineering/devops/create/code-review/)
- **Slack channels**:
  - [#g_create_code-review](https://gitlab.enterprise.slack.com/archives/C01EMBKS5DW)
  - [#g_create_code-review_alerts](https://gitlab.enterprise.slack.com/archives/C082E78PJJK)

Create:Code Review Group is responsible for all features about code review workflow (`feature_category` is
`code_review_workflow`). List of features can be found in this
[handbook page](https://handbook.gitlab.com/handbook/product/categories/features/#code-review).

## Services used

- [Web](../web/README.md) and [API](../api/README.md) for serving rails and API requests
- [Redis](../redis-cluster-cache/README.md) for caching
- [Sidekiq](../sidekiq/README.md) for asynchronous jobs
- Postgres for database
- Object storage for storing [external diffs](https://docs.gitlab.com/administration/merge_request_diffs/#using-object-storage)
- [Gitaly](../gitaly/README.md) for getting data from git

## Dashboards and links

### Grafana

- [Code Review Group error budget detail](https://dashboards.gitlab.net/d/stage-groups-detail-code_review) - this can help see which component (rails, graphql, or sidekiq) owned by Create:Code Review is failing
- [web: Rails Controller](https://dashboards.gitlab.net/d/web-rails-controller/web3a-rails-controller?var-controller=Projects::MergeRequestsController) - for getting information about specific Rails controller/actions
- [api: Rails Controller](https://dashboards.gitlab.net/d/api-rails-controller/api3a-rails-controller?var-action=GET%20%2Fapi%2Fprojects%2F:id%2Fmerge_requests) - for getting information about specific API endpoints
- [sidekiq: Worker Detail](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail?var-worker=UpdateMergeRequestsWorker) - for getting information about specific Sidekiq workers

### Kibana

- [Logs of failed Rails requests](https://log.gprd.gitlab.net/app/r/s/ang3B)
- [Logs of failed jobs](https://log.gprd.gitlab.net/app/r/s/wbhOW)

These logs show all failed Rails requests and jobs. They can be filtered by:

- Specific action/endpoint by `json.meta.caller_id`
- Specific job class by `json.class`
- By correlation ID by `json.correlation_id`

### Sentry

Errors can be found in [Sentry](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Acode_review_workflow&referrer=issue-list&statsPeriod=7d).

## Debugging

Here are some debugging steps for scenarios that we experienced before.

### Delayed or no updates on merge request page

Some updates like commits, diffs, and mergeability status that show on the merge request page
rely on Sidekiq workers. If Sidekiq workers are taking time to get jobs performed from the queue
or jobs are actually failing, they can result in outdated information.

The following workers are responsible for updating the said states:

- `UpdateMergeRequestsWorker`
- `MergeRequestMergeabilityCheckWorker`
- `MergeRequests::MergeabilityCheckBatchWorker`

To check how these workers are performing, look at these Grafana dashboards:

- [`UpdateMergeRequestsWorker`](https://dashboards.gitlab.net/goto/gwGYwYENR?orgId=1)
- [`MergeRequestMergeabilityCheckWorker` and `MergeRequests::MergeabilityCheckBatchWorker`](https://dashboards.gitlab.net/goto/jmIPQYPNg?orgId=1)

In these dashboards, see if apdex is going down, error ratio and queue length are going up compared
to normal levels. Look for sharp changes or sustained degradation rather than minor fluctuations.

If apdex is going down, it could be a sign that errors are up or the job is just too slow. If
queue length is up, it could mean that Sidekiq workers can't pick up jobs for some reason.

If jobs are too slow or queue length is up, see if it's not a widespread issue. Please refer
to [Sidekiq runbook](../sidekiq/README.md).

If errors are up, check Sentry for errors for those specific workers. Check the errors
and determine whether they're caused by another service failing or if it's caused by a bug
in application code. Here are links to filter errors on Sentry for those specific workers:

- [`UpdateMergeRequestsWorker`](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Acode_review_workflow+transaction%3ASidekiq%2FUpdateMergeRequestsWorker&referrer=issue-list&statsPeriod=7d)
- [`MergeRequestMergeabilityCheckWorker`](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Acode_review_workflow+transaction%3ASidekiq%2FMergeRequestMergeabilityCheckWorker&referrer=issue-list&statsPeriod=7d)
- [`MergeRequests::MergeabilityCheckBatchWorker`](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Acode_review_workflow+transaction%3ASidekiq%2FMergeRequests%3A%3AMergeabilityCheckBatchWorker&referrer=issue-list&statsPeriod=7d)

When errors seem to be caused by another service failure, please refer to that service's
runbook. Otherwise, reach out to Create:Code Review engineers for assistance.

### Web/API requests failing with HTTP 500

Create:Code Review group owns a number of different rails controllers and endpoints
and they can error out if there are issues in other services being used or a bug
in application code.

Check [Sentry](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Acode_review_workflow&referrer=issue-list&statsPeriod=7d)
for errors for the reported action/endpoint. Filter by `transaction` or by correlation ID
to focus on the specific failing action/endpoint.

If the error seems to be caused by another service failing, please refer to the runbook of that
service. If it is looking like a bug in application code, reach out to Create:Code Review
engineers for assistance.
