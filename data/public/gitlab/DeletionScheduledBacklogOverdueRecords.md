# DeletionScheduledBacklogOverdueRecords / DeletionScheduledBacklogOldestAgeTooHigh

## Overview

One or more projects or groups have been scheduled for deletion for longer
than they should be and still have not been removed. Deletions are backing
up instead of completing.

Two alerts share this runbook:

- **DeletionScheduledBacklogOverdueRecords** (primary) — the number of
  records overdue for deletion is above zero. This is the main signal and is
  not skewed by a single stuck record.
- **DeletionScheduledBacklogOldestAgeTooHigh** (backstop) — the oldest record
  awaiting deletion is older than the age threshold.


Common causes:

- A deletion worker (`ProjectDestroyWorker`, `GroupDestroyWorker`,
  `AdjournedProjectDeletionWorker`, `AdjournedGroupDeletionWorker`) keeps
  failing or rolling back, often on a statement timeout.
- The Sidekiq deletion queue is paused, starved, or backed up.
- One record can't be deleted because of a data problem, and it blocks the
  rest of the backlog behind it.

### Background

This alert exists because of
[INC-13111](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?search=INC-13111),
where deletions were silently broken on GitLab.com for over several days. A stuck
record looks exactly like one that is simply queued, so nothing paged. We
alert on how **overdue** the backlog is, not how **big** it is, so any future
deletion outage can only last so long before someone is notified.

## Services

- Team that owns this alert:
  [Organizations](https://handbook.gitlab.com/handbook/engineering/development/dev/tenant-scale/organizations/)
  (Tenant Scale section, `groups_and_projects` feature category).
- Underlying platform: the Sidekiq service, which runs the deletion workers and
  the sampler that emits these metrics.

## Metrics

Both metrics are emitted by the `DeletionScheduledBacklogSampler`, which runs
in Sidekiq every 5 minutes and is emitted into the `gitlab-gprd`,
`gitlab-gstg`, and `gitlab-pre` Mimir tenants
([gitlab-org/gitlab!252036](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/252036)).
Both projects and groups are covered, because scheduling either for deletion
sets `namespace_details.deletion_scheduled_at`.

- `gitlab_deletion_scheduled_backlog_overdue_count` — number of records whose
  `deletion_scheduled_at` is past their expected hard-deletion date (the
  `deletion_adjourned_period` setting plus a 2-day grace period).
- `gitlab_deletion_scheduled_backlog_oldest_age_seconds` — age of the oldest
  record still awaiting deletion in seconds. Normally low, dropping as
  records are deleted.

Thresholds:

- Overdue count: alert when `> 0`, sustained for 2 hours.
- Oldest age: alert when older than 32 days (the default
  `deletion_adjourned_period` of 30 days plus a 2-day grace period), sustained
  for 30 minutes.

Both are starting values and will be tuned before they can page — see
[Definitions](#definitions).

## Alert Behavior

- Both alerts clear automatically once the backlog drains below their
  thresholds.
- Silencing is appropriate only during a deliberate, tracked pause of deletion
  processing (for example, an open Change Request).
- These should be rare alerts. Under normal operation the backlog drains
  continuously and the overdue count sits at zero.

## Severities

- Default severity: `s3`, Slack-only (no `pager` label) while the thresholds
  are being tuned. Add the `pager: pagerduty` label (and raise the severity)
  to make it page once the thresholds are settled.
- This is not an outage — deletions are delayed, not lost. Customers may open
  Zendesk tickets about groups or projects that "won't delete."
- Raise the severity if the overdue count keeps climbing. That means the whole
  pipeline is stalled, not just one record blocking it.

## Verification

- Prometheus, on the affected environment at
  [dashboards.gitlab.net](https://dashboards.gitlab.net):
  - `max(gitlab_deletion_scheduled_backlog_overdue_count)`
  - `max(gitlab_deletion_scheduled_backlog_oldest_age_seconds)`
- Kibana: search Sidekiq logs for the failing deletion worker classes
  (`ProjectDestroyWorker`, `GroupDestroyWorker`,
  `AdjournedProjectDeletionWorker`, `AdjournedGroupDeletionWorker`) for
  exceptions or repeated rollbacks.

## Recent changes

- Check for recent deploys or database changes affecting the deletion services,
  and for open Change Requests that pause deletion processing.

## Troubleshooting

1. **Check the deletion workers in Kibana.** Look for exceptions, statement
   timeouts, or repeated rollbacks in `ProjectDestroyWorker` /
   `GroupDestroyWorker` and their adjourned-deletion cron workers.
2. **Check the Sidekiq deletion queues** are running and not paused or starved.
3. **Look for a single blocking record.** Query for the oldest record still in
   the backlog and inspect it for a data problem that fails deletion:

   ```ruby
   Namespace::Detail
     .where.not(deletion_scheduled_at: nil)
     .order(:deletion_scheduled_at)
     .first
   ```

4. **Re-drive deletion** for the affected record(s) once the underlying cause
   is fixed, and confirm the overdue count returns to zero.


## Escalation

- Primary contact: `#g_organizations` Slack channel
  ([team handbook](https://handbook.gitlab.com/handbook/engineering/development/dev/tenant-scale/organizations/)).
- For database-level blockers (statement timeouts, integrity errors preventing
  deletion), escalate to `#database_operations`.

## Definitions

- [Alert definition (Jsonnet source)](../../../libsonnet/alerts/deletion-scheduled-backlog-alerts.libsonnet)
- [Generator wiring](../../../mimir-rules-jsonnet/deletion-scheduled-backlog-alerts.jsonnet)
- Tunable values: the overdue-count `for:` window (2h), the 32-day age threshold,
  and the age `for:` window (30m). The age threshold mirrors the sampler's
  overdue cutoff (`deletion_adjourned_period` + 2-day slack); if
  `deletion_adjourned_period` on the tenant is not the 30-day default, adjust it.
  All are starting guesses and should be checked against a week of real data
  ([gitlab-org/gitlab#621640](https://gitlab.com/gitlab-org/gitlab/-/work_items/621640)).
  Only turn on paging once the alerts stop firing during normal operation.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/organizations/alerts/DeletionScheduledBacklogOverdueRecords.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related Organizations alerts](./)
- [Tracking issue: alert on the deletion-scheduled backlog](https://gitlab.com/gitlab-org/gitlab/-/work_items/621640)
- [Metric MR](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/252036)
