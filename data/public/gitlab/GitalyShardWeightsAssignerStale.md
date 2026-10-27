# GitalyShardWeightsAssignerStale

## Overview

This alert is triggered when the `gitaly-shard-weights-assigner` (the shard rebalancer) has not completed a successful run for longer than its staleness threshold. The assigner runs daily as a scheduled pipeline on ops.gitlab.net and reassigns Gitaly storage shard weights based on each shard's available disk space, so that new repositories are placed on shards with capacity.

When the assigner stops succeeding, shard weights go stale: new repositories continue to be placed according to the last weights written, even as those shards fill up. Over time this erodes disk headroom on the active shards and can leave the fleet without capacity for new repositories. Known causes include:

- An expired or invalid `TARGET_API_PRIVATE_TOKEN` ([INC-11283](https://app.incident.io/gitlab/incidents/11283)).
- The Prometheus pushgateway being unreachable, so that even a successful run fails to publish its completion metric and the deadman goes stale (a past failure was caused by a changed pushgateway IP).
- The Mimir query API being unavailable, so the job cannot read available disk space and aborts.

This alert is a deadman switch: it fires on the *absence* of a recent success rather than on an explicit failure, so it also catches the case where the job stops running entirely.

## Services

Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Metrics

This alert is based on the job-completion (deadman) metric `gitlab_job_success_timestamp_seconds`, which the assigner publishes to a Prometheus pushgateway with labels `resource="assign_weights"`, `tier="stor"`, and `exported_type="gitaly-shard-weight-assigner"`. The metric records the Unix timestamp of the last successful run; the alert measures how long ago that was, in seconds.

The alert is generated for both production (`env="gprd"`, `mimir-gitlab-gprd` datasource) and staging (`env="gstg"`, `mimir-gitlab-gstg` datasource), since a scheduled assigner job runs in each environment.

The threshold is set above the job's daily cadence so that normal scheduling jitter or a single slow run does not page, while a genuinely missed daily run is still caught promptly. Under normal conditions the last-success timestamp advances every ~24 hours, so the measured age stays well below the threshold.

Explore the underlying metric in Grafana:

- [Age of last successful run (gprd)](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swa1%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gprd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22time%28%29%20-%20max%28gitlab_job_success_timestamp_seconds%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gprd%5C%22%7D%29%20by%20%28env%29%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gprd%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1): the exact value this alert evaluates (`time() - max(gitlab_job_success_timestamp_seconds{resource="assign_weights", env="gprd"}) by (env)`).
- [Age of last successful run (gstg)](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swa1g%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gstg%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22time%28%29%20-%20max%28gitlab_job_success_timestamp_seconds%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gstg%5C%22%7D%29%20by%20%28env%29%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gstg%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1): the same value in staging.

The exact query and threshold value are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Alert Behavior

This alert fires when the age of the last successful run exceeds the staleness threshold for the rule's `for` duration. At that point the daily rebalancing has effectively stopped and weights are no longer being updated.

There are no automated silencing rules. Silence only if the staleness is known and expected, for example while the schedule is intentionally deactivated during a Gitaly fleet expansion (the assigner is paused while new storages are added).

The alert expression and `for` duration are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Severities

Production (`gprd`) is **s2** and pages (`pager: pagerduty`). Staging (`gstg`) is **s4**, non-paging, and blackholed.

There is no immediate end-user impact when the alert first fires, but prolonged staleness directly contributed to a disk-saturation incident on the Gitaly fleet. To gauge severity, check how long the job has been stale (a single missed run versus weeks) and the current disk headroom on the active Gitaly shards.

## Verification

- Inspect the most recent run on the [gitaly-shard-weights-assigner pipeline schedules](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner/-/pipeline_schedules): confirm the schedule is active, and check when it last ran and whether that run passed.
- Open the latest pipeline's job log to see whether the job is failing, stalling, or not triggering at all.
- Confirm the deadman metric itself is being received by querying [`gitlab_job_success_timestamp_seconds{resource="assign_weights", env="gprd"}`](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swa1%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gprd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22time%28%29%20-%20max%28gitlab_job_success_timestamp_seconds%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gprd%5C%22%7D%29%20by%20%28env%29%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gprd%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1)).

## Recent changes

- The assigner is intentionally deactivated during Gitaly fleet expansions while new storages are provisioned, then reactivated; an expansion in progress is a common benign reason for staleness. See the related production change requests in [gitlab-com/gl-infra/production](https://gitlab.com/gitlab-com/gl-infra/production).
- The job's schedule and credentials are configured in the [gitaly-shard-weights-assigner project](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner) on ops.gitlab.net (pipeline schedule variables and CI/CD settings).

## Troubleshooting

Under normal operation the daily run keeps the last-success age well below the threshold. Staleness almost always traces back to the job no longer being able to run to completion. Prioritize finding why the most recent run did not succeed.

1. Open the [latest scheduled pipeline](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner/-/pipeline_schedules) and read the most recent job log for the failure or stall reason.
2. **Check the token first.** An expired or invalid `TARGET_API_PRIVATE_TOKEN` (the [INC-11283](https://app.incident.io/gitlab/incidents/11283) root cause). Confirm the token is present and valid, and rotate it if needed.
3. Check pushgateway reachability. If the run succeeds but the completion metric is not published (e.g. a changed pushgateway IP or a firewall change), the deadman will still go stale. Verify the `gitlab_job_success_timestamp_seconds{resource="assign_weights"}` series is advancing.
4. Check the Mimir query path. If the job cannot read shard disk-space metrics it will abort before writing weights.
5. Rule out an intentional pause: confirm the schedule has not been deactivated for an in-progress fleet expansion.
6. Once the cause is fixed, re-run the schedule manually and confirm the run succeeds and the last-success timestamp advances.

## Possible Resolutions

- [INC-11283](https://app.incident.io/gitlab/incidents/11283): a bad/expired `TARGET_API_PRIVATE_TOKEN` caused the job to silently stop running contributing to Gitaly disk saturation. Resolved by fixing the token and restoring the daily run. Related: [production#22346](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22346).

## Dependencies

Internal and external dependencies which could potentially cause this alert:

- **ops.gitlab.net scheduled pipelines**: the runner and schedule that execute the daily job; a deactivated schedule or runner outage stops the job entirely.
- **`TARGET_API_PRIVATE_TOKEN`**: the credential used to read and write repository storage weights via the GitLab API; an expired or invalid token is the most common cause.
- **Prometheus pushgateway**: receives the job-completion metric; if unreachable, the deadman goes stale even on otherwise successful runs.
- **Mimir/Prometheus query API**: provides the shard available-disk-space metrics the job needs to compute weights.

## Escalation

If the issue cannot be resolved quickly, escalate to the appropriate engineering or operations team for further investigation. Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Definitions

The definition for this alert can be found at:

- [gitaly-shard-weights-assigner-alerts.libsonnet](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/gitaly-shard-weights-assigner-alerts.libsonnet)
- [gitaly-shard-weights-assigner alerts (gitlab-gprd)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly-shard-weights-assigner/autogenerated-gitlab-gprd-gitaly-shard-weights-assigner-gitaly-shard-weights-assigner-alerts.yml)
- [gitaly-shard-weights-assigner alerts (gitlab-gstg)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/gitaly-shard-weights-assigner/autogenerated-gitlab-gstg-gitaly-shard-weights-assigner-gitaly-shard-weights-assigner-alerts.yml)

The staleness threshold assumes the job's daily cadence; keep it above ~24h so normal jitter does not flap the alert, and below ~48h so a single missed run is still caught promptly.

## Related Links

- [Gitaly service](../README.md)
- [GitalyShardWeightsAssignerFailed](./GitalyShardWeightsAssignerFailed.md): the companion alert that fires on an explicit job failure
- [GitLab Job Completion](../../uncategorized/job_completion.md): the deadman/job-completion metric convention this alert is built on
- [Related alerts](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/gitaly/alerts?ref_type=heads)
