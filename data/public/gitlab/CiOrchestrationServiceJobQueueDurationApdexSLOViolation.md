# Job Queue Duration Apdex SLO Violations

Covers:

- `CiOrchestrationServiceSharedRunnerJobQueueDurationApdexSLOViolation`
- `CiOrchestrationServiceNonSharedRunnerJobQueueDurationApdexSLOViolation`

## Overview

These alerts fire when the job queue duration apdex for shared or non-shared runners violates its SLO burn rate threshold, indicating that jobs are waiting too long in the pending state before being picked up by a runner.

The `job_queue_duration_seconds` histogram measures the time between job creation and runner assignment, emitted when a runner picks up a job via `POST /api/v4/jobs/request`. Separate SLIs track shared runners (SaaS-managed) and non-shared runners (project/group runners).

### Impact

- Longer pipeline durations due to queueing delays
- Developer feedback loops slowed
- Shared runner impact: affects all GitLab.com users without self-managed runners
- Non-shared runner impact: typically affects specific projects or groups

### Contributing Factors

**Shared runners:**

- Runner fleet capacity insufficient for demand
- Autoscaling delays in provisioning new runners
- Runner pod evictions or node failures
- Surge in CI demand (e.g., mass retries after flaky test fix)

**Non-shared runners:**

- Project/group runners offline or misconfigured
- Tag mismatches (jobs requiring tags that no runner provides)
- Runner concurrency limits reached
- Plan-gating: `no_matching_runner` due to `allowed_plans` restrictions (results in `stuck_or_timeout_failure` after 24h)

## Services

- [ci-orchestration service overview](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview)
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability)
- **Team**: [Verify](https://handbook.gitlab.com/handbook/engineering/devops/verify/)
- **Slack**: `#s_verify_alerts`

## Metrics

### Shared Runner Job Queue Duration

Uses `job_queue_duration_seconds_bucket{shared_runner="true"}` with `histogramApdex`.

- **Satisfied threshold**: 1 second (jobs picked up within 1s are "satisfactory")
- **SLO**: 90% apdex
- **MWMBR fires at**: < 40% (6h window). The 1h window threshold computes to < -44%, which is below 0% and therefore mathematically impossible — in practice, only the 6h window can trigger this alert.

### Non-Shared Runner Job Queue Duration

Uses `job_queue_duration_seconds_bucket{shared_runner="false"}` with `histogramApdex`.

- **Satisfied threshold**: 30 seconds
- **SLO**: 95% apdex
- **MWMBR fires at**: < 70% (6h window) / < 28% (1h window)

### Histogram Bucket Boundaries

`1, 3, 10, 30, 60, 300, 900, 1800, 3600, +Inf` seconds. The `metricsFormat='migrating'` handles both Prometheus 2 (integer) and Prometheus 3 (float) bucket label formats.

## Alert Behavior

- Severity: S3 (Slack-only, no paging)
- Routes to: `#s_verify_alerts`
- MWMBR requires both short and long windows to breach simultaneously
- Non-shared runner queue duration is inherently noisier (depends on customer runner fleet availability)
- **Silencing**: Safe to silence during known runner fleet maintenance or capacity scaling events. Use Alertmanager silence with matchers `type=ci-orchestration, component=~.*job_queue_duration`
- **Expected frequency**: Shared runner alerts should be rare. Non-shared runner alerts may fire more frequently due to customer runner fleet variability

## Severities

Default severity is S3. Consider upgrading to S2 if:

- Shared runner queue duration p90 > 5 minutes sustained
- Runner fleet-wide issue affecting all shared runner jobs
- Correlated customer reports of jobs stuck in pending

## Verification

```promql
# Shared runner queue duration apdex
gitlab_component_apdex:ratio_5m{component="shared_runner_job_queue_duration", type="ci-orchestration", environment="gprd"}

# Non-shared runner queue duration apdex
gitlab_component_apdex:ratio_5m{component="non_shared_runner_job_queue_duration", type="ci-orchestration", environment="gprd"}

# Queue duration percentiles (shared)
histogram_quantile(0.90, sum by (le) (sli_aggregations:job_queue_duration_seconds_bucket:rate_5m{environment="gprd", shared_runner="true"}))

# Queue duration percentiles (non-shared)
histogram_quantile(0.90, sum by (le) (sli_aggregations:job_queue_duration_seconds_bucket:rate_5m{environment="gprd", shared_runner="false"}))
```

- [ci-orchestration service overview dashboard](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview) — burn rate panels
- [Pipeline Observability dashboard — Job Queueing section](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — heatmaps and percentile trends

## Recent Changes

- [Production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)
- [Runner configuration changes](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests)
- [Infrastructure changes](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests)

## Troubleshooting

### 1. Check Runner Fleet Capacity (Shared)

- [CI Runners dashboard](https://dashboards.gitlab.net/d/ci-runners-main) for runner availability and saturation
- Check pending jobs queue length vs. runner capacity
- Look for autoscaling issues or GCP quota limits

### 2. Check for Tag Mismatches (Non-Shared)

Non-shared runner queue duration issues are often caused by jobs requesting tags that no available runner provides. This results in jobs sitting in pending indefinitely (until `stuck_or_timeout_failure` at 24h).

### 3. Check Job Pickup Rate

The "Job pickup rate" panel on the Pipeline Observability dashboard shows how quickly jobs are being assigned to runners. A declining pickup rate with stable creation rate indicates runner capacity issues.

### 4. Check for Demand Spikes

Unusual spikes in `pipelines_created_total` or job creation rate can overwhelm runner capacity:

- Mass retries after a flaky test fix
- Scheduled pipeline bursts
- Large merge train activity

## Possible Resolutions

No past incidents have been recorded yet for this alert. This section will be updated as incidents occur.

## Dependencies

- **CI Runners (shared)**: SaaS runner fleet capacity and health
- **Project/Group Runners (non-shared)**: Customer-managed runner availability
- **Rails API**: Job assignment endpoint (`/api/v4/jobs/request`)

## Escalation

### When to Escalate

- Shared runner queue p90 > 10 minutes for > 30 minutes
- Runner fleet capacity appears exhausted
- Correlated with runner service degradation

### Support Channels

- `#s_verify_alerts` (primary)
- `#g_runner` (Runner team)
- `#f_hosted_runners_on_linux` (Hosted Runners)
- `#production` (if S2+ severity)

## Definitions

- [SLI definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/ci-orchestration.jsonnet)
- [Alert rules](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/ci-orchestration/autogenerated-gitlab-gprd-ci-orchestration-service-level-alerts.yml)
- [Edit this runbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/ci-orchestration/alerts/CiOrchestrationServiceJobQueueDurationApdexSLOViolation.md)

## Related Links

- [All ci-orchestration alerts](./)
- [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
- [CI Runners runbooks](../../ci-runners/README.md)
