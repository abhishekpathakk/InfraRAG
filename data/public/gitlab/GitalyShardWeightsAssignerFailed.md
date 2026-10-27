# GitalyShardWeightsAssignerFailed

## Overview

This alert is triggered when the `gitaly-shard-weights-assigner` (the shard rebalancer) reports a failure on its most recent run. The assigner runs daily as a scheduled pipeline on ops.gitlab.net and reassigns Gitaly storage shard weights based on each shard's available disk space, so that new repositories are placed on shards with capacity.

When a run fails, shard weights are not updated. A single transient failure is usually harmless because the next daily run corrects it, but persistent failures mean weights stop tracking real disk usage: new repositories continue to be placed according to stale weights even as shards fill up, eroding disk headroom on the active shards. Known causes include:

- An expired or invalid `TARGET_API_PRIVATE_TOKEN` ([INC-11283](https://app.incident.io/gitlab/incidents/11283)).
- Mimir query authentication errors, so the job cannot read available disk space.
- The Prometheus pushgateway being unreachable.

Unlike its companion [GitalyShardWeightsAssignerStale](./GitalyShardWeightsAssignerStale.md) deadman alert (which fires on the *absence* of a recent success), this alert fires on an *explicit* failure signal from the job.

## Services

Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Metrics

This alert is based on the job-failure metric `gitlab_job_failed`, which the assigner publishes to a Prometheus pushgateway with labels `resource="assign_weights"`, `tier="stor"`, and `exported_type="gitaly-shard-weight-assigner"`. It is a boolean gauge: a run sets it to `1` on failure, and a subsequent successful run clears it back to `0`.

The alert is generated for both production (`env="gprd"`, `mimir-gitlab-gprd` datasource) and staging (`env="gstg"`, `mimir-gitlab-gstg` datasource), since a scheduled assigner job runs in each environment.

The `for` duration is set so that a same-day failure has a chance to self-recover on the next scheduled (daily) run before the alert pages, while a failure that persists across runs still escalates. Under normal conditions a successful run keeps the flag at `0`.

Explore the underlying metric in Grafana:

- [Job failure flag (gprd)](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swaf%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gprd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22gitlab_job_failed%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gprd%5C%22%7D%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gprd%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1): the raw `gitlab_job_failed{resource="assign_weights", env="gprd"}` series this alert evaluates; values flapping between `1` and `0` indicate runs failing and then recovering.
- [Job failure flag (gstg)](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swafg%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gstg%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22gitlab_job_failed%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gstg%5C%22%7D%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gstg%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1): the same flag in staging.

The exact query and `for` duration are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Alert Behavior

This alert fires when the job-failure flag stays at `1` for the rule's `for` duration, i.e. a failure that is not cleared by a subsequent successful run within that window.

There are no automated silencing rules. Silence only if the failure is known and a fix is already in flight.

The alert expression and `for` duration are defined in code and may change over time; see the [Definitions](#definitions) section for the authoritative values.

## Severities

Production (`gprd`) is **s2** and pages (`pager: pagerduty`). Staging (`gstg`) is **s4**, non-paging, and blackholed.

There is no immediate end-user impact from a single failed run, but persistent failures stop weight rebalancing and contributed to a disk-saturation incident on the Gitaly fleet. To gauge severity, determine whether the failure is transient or recurring and check the current disk headroom on the active Gitaly shards.

## Verification

- Inspect the most recent run on the [gitaly-shard-weights-assigner pipeline schedules](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner/-/pipeline_schedules) and confirm whether the latest run failed.
- Open the failing pipeline's job log to read the exact failure reason.
- Query [`gitlab_job_failed{resource="assign_weights", env="gprd"}`](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22swaf%22%3A%7B%22datasource%22%3A%22mimir-gitlab-gprd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22expr%22%3A%22gitlab_job_failed%7Bresource%3D%5C%22assign_weights%5C%22%2C%20env%3D%5C%22gprd%5C%22%7D%22%2C%22range%22%3Atrue%2C%22instant%22%3Atrue%2C%22datasource%22%3A%7B%22type%22%3A%22prometheus%22%2C%22uid%22%3A%22mimir-gitlab-gprd%22%7D%2C%22editorMode%22%3A%22code%22%2C%22legendFormat%22%3A%22__auto%22%7D%5D%2C%22range%22%3A%7B%22from%22%3A%22now-7d%22%2C%22to%22%3A%22now%22%7D%7D%7D&orgId=1) to confirm the flag is set and to see whether prior runs have been flapping between success and failure.

## Recent changes

- The assigner is intentionally deactivated during Gitaly fleet expansions while new storages are provisioned, then reactivated. The job's schedule and credentials are configured in the [gitaly-shard-weights-assigner project](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner) on ops.gitlab.net.
- Related production change requests are tracked in [gitlab-com/gl-infra/production](https://gitlab.com/gitlab-com/gl-infra/production).

## Troubleshooting

Under normal operation the daily run succeeds and the failure flag stays at `0`. A failure that persists past the `for` window almost always points to a broken credential or dependency rather than a transient blip. Read the job log first.

1. Open the latest pipeline job log via the [pipeline schedules](https://ops.gitlab.net/gitlab-com/gl-infra/gitaly-shard-weights-assigner/-/pipeline_schedules) and read the failure reason.
2. Map the failure to its likely cause:
   - **Authorization errors against the GitLab API** → expired/invalid `TARGET_API_PRIVATE_TOKEN` (the [INC-11283](https://app.incident.io/gitlab/incidents/11283) root cause); rotate the token.
   - **Mimir query auth/connection errors** → the job cannot read shard disk-space metrics; check the Mimir query credentials and endpoint.
   - **Pushgateway connection errors** → the completion/failure metric cannot be published (e.g. a changed pushgateway IP or firewall change).
3. Once the cause is fixed, re-run the schedule manually and confirm the next run succeeds and clears the failure flag.

## Possible Resolutions

- [INC-11283](https://app.incident.io/gitlab/incidents/11283): a bad/expired `TARGET_API_PRIVATE_TOKEN` caused the job to silently stop running contributing to Gitaly disk saturation. Resolved by fixing the token and restoring the daily run. Related: [production#22346](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22346).

## Dependencies

Internal and external dependencies which could potentially cause this alert:

- **`TARGET_API_PRIVATE_TOKEN`**: the credential used to read and write repository storage weights via the GitLab API; an expired or invalid token is the most common cause of failure.
- **Mimir/Prometheus query API**: provides the shard available-disk-space metrics the job needs to compute weights; auth or connectivity errors fail the run.
- **Prometheus pushgateway**: receives the job-failure/job-completion metrics; connectivity errors fail the publish step.
- **ops.gitlab.net scheduled pipelines**: the runner and schedule that execute the daily job.

## Escalation

If the issue cannot be resolved quickly, escalate to the appropriate engineering or operations team for further investigation. Refer to the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services) for the service owners and escalation.

## Definitions

The definition for this alert can be found at:

- [gitaly-shard-weights-assigner-alerts.libsonnet](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/gitaly-shard-weights-assigner-alerts.libsonnet)
- [gitaly-shard-weights-assigner alerts (gitlab-gprd)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly-shard-weights-assigner/autogenerated-gitlab-gprd-gitaly-shard-weights-assigner-gitaly-shard-weights-assigner-alerts.yml)
- [gitaly-shard-weights-assigner alerts (gitlab-gstg)](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/gitaly-shard-weights-assigner/autogenerated-gitlab-gstg-gitaly-shard-weights-assigner-gitaly-shard-weights-assigner-alerts.yml)

The `for` duration lets a same-day failure self-recover on the next daily run; keep it below the daily cadence so that failures persisting across runs still page.

## Related Links

- [Gitaly service](../README.md)
- [GitalyShardWeightsAssignerStale](./GitalyShardWeightsAssignerStale.md): the companion deadman alert that fires when no successful run is seen
- [GitLab Job Completion](../../uncategorized/job_completion.md): the deadman/job-completion metric convention this alert is built on
- [Related alerts](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/gitaly/alerts?ref_type=heads)
