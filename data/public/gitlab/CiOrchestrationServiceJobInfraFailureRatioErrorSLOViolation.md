# CiOrchestrationServiceJobInfraFailureRatioErrorSLOViolation

## Overview

This alert fires when the infra-attributable share of CI job failures **on GitLab-operated (instance) runners** exceeds its SLO burn rate threshold, indicating that an unusually high proportion of job failures are caused by infrastructure issues rather than user errors.

The `job_infra_failure_ratio` SLI uses `gitlab_ci_job_failure_reasons` as both numerator and denominator, with **both scoped to `runner_type="instance_type"`** so the ratio reflects only failures on runners the platform operates. The error rate is the fraction of instance-runner job failures whose `reason` label matches an **explicit positive list** of infra-attributable reasons (e.g., `runner_system_failure`, `scheduler_failure`, `data_integrity_failure`). All other reasons — user/external errors like `script_failure`, and ambiguous reasons like `unknown_failure` — only contribute to the denominator. They are tracked separately in the Pipeline Observability dashboard's "Job Failures" panels for anomaly detection.

Failures on customer-operated (`group_type`/`project_type`) runners are excluded because their availability is outside platform control, mirroring the `non_shared_runner_job_queue_duration` attribution decision. The all-ownership breakdown remains visible on the Pipeline Observability dashboard's "Job Failures" panels.

The positive list lives in [`metrics-catalog/services/lib/ci-job-failure-reasons.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/lib/ci-job-failure-reasons.libsonnet) (`systemCausedReasons`) and is the single source of truth used by both the SLI and the dashboard.

### Impact

- CI jobs failing for reasons outside user control
- Reduced pipeline success rates across the platform
- User frustration and wasted compute (retries)
- Potential data integrity issues if `data_integrity_failure` is elevated

### Contributing Factors

Each entry is a reason in `systemCausedReasons` and a typical underlying cause. Under the `instance_type` scope, only reasons that can carry an assigned runner contribute to this SLI:

- `runner_system_failure`: Runner panics, Kubernetes pod disruptions, trace patch failures, network egress issues
- `scheduler_failure`: Sidekiq job-scheduling failures
- `data_integrity_failure`: Internal consistency errors
- `job_router_failure`: Internal Job Router service failures
- `no_updates_running` / `no_updates_canceling`: Job state machine not receiving heartbeats
- Gitaly overload causing clone/fetch failures (surfaces as `runner_system_failure`)
- Registry/Dependency Proxy issues causing image-pull failures (surfaces as `runner_system_failure`)

The following reasons are in `systemCausedReasons` but are **excluded under the `instance_type` scope** because they are almost always emitted with `runner_type="none"`, since no runner is assigned. These pickup-time/queueing failures are covered by `shared_runner_job_queue_duration{shared_runner="true"}`:

- `stuck_pending_with_matching_runners`: Jobs stuck pending despite available matching runners
- `stale_schedule`: Delayed jobs (`when: delayed`) left in `scheduled` state > 1h past their `scheduled_at`, dropped by `Ci::StuckBuilds::DropScheduledService`
- `environment_creation_failure`: Failure to create a deployment environment (set during pipeline processing, before runner assignment)
- `stuck_or_timeout_failure` (legacy): retained for backward compatibility — pre-19.0 in-flight jobs and historical data ([gitlab#595752](https://gitlab.com/gitlab-org/gitlab/-/issues/595752))

## Services

- [ci-orchestration service overview](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview)
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability)
- **Team**: [Verify](https://handbook.gitlab.com/handbook/engineering/devops/verify/)
- **Slack**: `#s_verify_alerts`

## Metrics

The SLI uses the same metric for both request rate and error rate:

- **Request rate**: `rate(gitlab_ci_job_failure_reasons{runner_type="instance_type"}[5m])` — all instance-runner job failures
- **Error rate**: `rate(gitlab_ci_job_failure_reasons{reason=~"<infra-attributable reasons>",runner_type="instance_type"}[5m])` — instance-runner failures whose `reason` matches the positive include list (source of truth: [`services/lib/ci-job-failure-reasons.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/lib/ci-job-failure-reasons.libsonnet))
- **Emitted by**: `api`, `sidekiq`, `web`
- **SLO**: 95% success rate (errorRatio: 0.95, meaning max 5% infra failure share)
- **MWMBR fires at**: > 30% infra share (6h window) / > 72% (1h window — in practice dominated by the 6h window)

### Counted reasons (infra-attributable)

The positive include list is defined in [`services/lib/ci-job-failure-reasons.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/lib/ci-job-failure-reasons.libsonnet) as `systemCausedReasons`. The `runner_type` filter stacks on top of it: under the `instance_type` scope, only reasons that can carry an assigned runner actually contribute:

`runner_system_failure`, `scheduler_failure`, `no_updates_running`, `no_updates_canceling`, `data_integrity_failure`, `job_router_failure`

The remaining `systemCausedReasons` entries — `stuck_pending_with_matching_runners`, `stale_schedule`, `environment_creation_failure`, and legacy `stuck_or_timeout_failure` — are almost always emitted with `runner_type="none"`, since no runner is assigned, and are therefore excluded by the `instance_type` scope. They remain in the shared reason set for the all-ownership dashboard panels, and their queueing signal is covered by `shared_runner_job_queue_duration{shared_runner="true"}`.

### Reasons NOT counted

Every other `reason` value is treated as non-infra and contributes only to the denominator. Notable examples:

- User/external-attributable: `script_failure`, `ci_quota_exceeded`, `no_matching_runner`, `runner_unsupported`, `job_execution_timeout`, `missing_dependency_failure`, etc.
- Ambiguous: `unknown_failure` (catch-all for unrecognised runner-side failure reasons)
- Runner-classified (introduced via [gitlab#595703](https://gitlab.com/gitlab-org/gitlab/-/work_items/595703)): `runner_configuration_error`, `runner_external_dependency_failure`, `runner_interrupted`

These appear in the Pipeline Observability dashboard's "Job failures - others" panels for separate anomaly detection.

## Alert Behavior

- Severity: S3 (Slack-only, no paging)
- Routes to: `#s_verify_alerts`
- MWMBR requires both the short window (5m/1h) and long window (30m/6h) to breach simultaneously
- The ratio can spike during incidents affecting runners or Gitaly
- **Silencing**: Safe to silence during known runner fleet maintenance or Gitaly incidents where the root cause is already being addressed. Use Alertmanager silence with matchers `type=ci-orchestration, component=job_infra_failure_ratio`
- **Expected frequency**: May fire during infrastructure incidents. Under normal conditions, the infra failure share is well below the 5% SLO ceiling

## Severities

Default severity is S3. Consider upgrading to S2 if:

- Infra failure ratio > 5% sustained for > 30 minutes
- A single failure reason dominates (e.g., `runner_system_failure` spike indicating fleet-wide runner issue)
- Correlated with multiple customer reports

## Verification

```promql
# Current infra failure ratio (pre-aggregated)
gitlab_component_errors:ratio_5m{component="job_infra_failure_ratio", type="ci-orchestration", environment="gprd"}

# Breakdown by infra failure reason on instance runners (matches the SLI).
# The recording rule is already scoped to runner_type="instance_type"; the
# explicit selector below documents that scope.
sum by (reason) (sli_aggregations:gitlab_ci_job_failure_reasons:rate_5m{environment="gprd", runner_type="instance_type", reason=~"runner_system_failure|scheduler_failure|no_updates_running|no_updates_canceling|data_integrity_failure|job_router_failure"})

# All other reasons across all runner ownership (non-infra), for context.
# Uses the raw counter (not the instance-scoped recording rule) so this stays
# a genuine all-ownership view.
sum by (reason) (rate(gitlab_ci_job_failure_reasons{environment="gprd", reason!~"runner_system_failure|scheduler_failure|stuck_pending_with_matching_runners|no_updates_running|no_updates_canceling|data_integrity_failure|environment_creation_failure|job_router_failure|stale_schedule|stuck_or_timeout_failure"}[5m]))
```

- [ci-orchestration service overview dashboard](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview) — burn rate panels
- [Pipeline Observability dashboard — Job Failures section](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — per-reason breakdown by runner ownership

## Recent Changes

- [Production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)
- [Runner configuration changes](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests)

## Troubleshooting

### 1. Identify the Dominant Failure Reason

Check the "Job failures - system-caused - GitLab runners" panel on the Pipeline Observability dashboard's "Job Failures" section. The top reason by volume tells you where to investigate:

| Reason | Investigate |
| ------ | ----------- |
| `runner_system_failure` | Runner fleet health, Kubernetes node issues, runner manager logs, network egress |
| `scheduler_failure` | Sidekiq scheduling issues |
| `data_integrity_failure` | Database consistency, recent migrations |
| `job_router_failure` | Internal Job Router service |
| `no_updates_running` / `no_updates_canceling` | Runner heartbeat / job-state-machine issues |

> Pickup-time reasons (`stuck_pending_with_matching_runners`, `stale_schedule`, `environment_creation_failure`, legacy `stuck_or_timeout_failure`) are `runner_type="none"` and do **not** contribute to this instance-scoped SLI. If a pickup/queueing problem is suspected, check `shared_runner_job_queue_duration` and the "Job failures - system-caused - no runner" panel instead.

> `unknown_failure` is **not** counted by this SLI. If it dominates on the "Job failures - others" panels, investigate runner-side failure reasons not recognised by Rails (often pointing to a new Runner version emitting an unmapped string).

### 2. Check Runner Fleet Health

- [CI Runners dashboard](https://dashboards.gitlab.net/d/ci-runners-main) for runner availability
- Look for node-level issues, pod evictions, or autoscaling problems

### 3. Check Gitaly Health

Gitaly overload causes job clone/fetch failures that surface as `runner_system_failure`:

- [Gitaly dashboard](https://dashboards.gitlab.net/d/gitaly-main) for latency and error rates

### 4. Check Registry/Dependency Proxy

Image pull failures also surface as `runner_system_failure`:

- [Registry dashboard](https://dashboards.gitlab.net/d/registry-main) for error rates

### 5. Check for Incident Correlation

Infrastructure incidents (Gitaly DDoS, runner fleet issues, database problems) often cause spikes in this SLI. Check `#production` and `#incident-management` for ongoing incidents.

## Possible Resolutions

No past incidents have been recorded yet for this alert. This section will be updated as incidents occur.

## Dependencies

- **CI Runners**: Runner fleet availability and health
- **Gitaly**: Git clone/fetch operations within jobs
- **Container Registry**: Image pulls for job containers
- **PostgreSQL (CI)**: Job state recording

## Escalation

### When to Escalate

- Single failure reason > 20% of total failures
- `runner_system_failure` spike correlated with runner fleet degradation
- Alert persists > 1 hour with no identified cause

### Support Channels

- `#s_verify_alerts` (primary)
- `#g_runner` (Runner team — for runner_system_failure)
- `#g_pipeline-execution` (Pipeline Execution team)
- `#production` (if S2+ severity)

## Definitions

- [SLI definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/ci-orchestration.jsonnet)
- [Alert rules](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/ci-orchestration/autogenerated-gitlab-gprd-ci-orchestration-service-level-alerts.yml)
- [Failure reason classification](https://gitlab.com/gitlab-org/gitlab/-/work_items/595703)
- [Edit this runbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/ci-orchestration/alerts/CiOrchestrationServiceJobInfraFailureRatioErrorSLOViolation.md)

## Related Links

- [All ci-orchestration alerts](./)
- [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
- [DX Failure Analysis Dashboard](https://dashboards.gitlab.net/d/dx-failure-analysis/)
- [Standardize CI job failure reasons](https://gitlab.com/gitlab-org/gitlab/-/work_items/595703)
