# Pipeline Creation Sidekiq Worker SLO Violations

Covers:

- `CiOrchestrationServicePipelineCreationSidekiqQueueDurationApdexSLOViolation`
- `CiOrchestrationServicePipelineCreationSidekiqExecutionApdexSLOViolation`
- `CiOrchestrationServicePipelineCreationSidekiqExecutionErrorSLOViolation`

## Overview

These alerts fire when pipeline creation Sidekiq workers violate their SLO burn rate thresholds, indicating that pipeline creation is either slow (apdex) or failing (error rate).

Pipeline creation workers (matching `.*CreatePipelineWorker.*`) handle the initial processing when a user pushes, opens an MR, or triggers a pipeline via API. Degradation here directly impacts the time between a user action and the pipeline appearing in the UI.

### Impact

- Delayed pipeline creation after pushes or MR events
- Users experience a delay between pushing a commit and seeing the pipeline appear on the merge request widget or the **CI/CD > Pipelines** page
- Increased queue depth in Sidekiq, potentially cascading to other workers
- If error rate is elevated: pipelines silently failing to create

### Contributing Factors

- Sidekiq queue congestion (too many jobs, not enough workers)
- Database contention (CI tables under heavy load)
- Gitaly latency (pipeline creation reads many files from the repo, such as `.gitlab-ci.yml`)
- Application errors in pipeline chain processing (config parsing, rule evaluation)
- Deployment or feature flag changes affecting pipeline creation path

## Services

- [ci-orchestration service overview](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview)
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability)
- **Team**: [Verify](https://handbook.gitlab.com/handbook/engineering/devops/verify/)
- **Slack**: `#s_verify_alerts`

## Metrics

### Queue Duration Apdex

The queueing apdex measures how quickly pipeline creation jobs are dequeued by Sidekiq workers. Uses `gitlab_sli_sidekiq_queueing_apdex_success_total` / `gitlab_sli_sidekiq_queueing_apdex_total` filtered to `worker=~".*CreatePipelineWorker.*"`.

- **SLO**: 99% apdex
- **MWMBR fires at**: < 94% (6h window) / < 85.6% (1h window)
- **Satisfied threshold**: defined by the worker's urgency attribute

### Execution Apdex

The execution apdex measures how quickly pipeline creation jobs complete once dequeued. Uses `gitlab_sli_sidekiq_execution_apdex_success_total` / `gitlab_sli_sidekiq_execution_apdex_total`.

- **SLO**: 99% apdex
- **MWMBR fires at**: < 94% (6h window) / < 85.6% (1h window)

### Execution Error Rate

The error rate measures the fraction of pipeline creation jobs that fail. Uses `gitlab_sli_sidekiq_execution_error_total` / `gitlab_sli_sidekiq_execution_total`.

- **SLO**: 99.95% success rate (errorRatio: 0.9995)
- **MWMBR fires at**: > 0.3% error rate (6h window) / > 0.72% (1h window)

## Alert Behavior

- Severity: S3 (Slack-only, no paging)
- Routes to: `#s_verify_alerts`
- MWMBR requires both the short window (5m/1h) and long window (30m/6h) to breach simultaneously
- Brief spikes (< 5 minutes) will not fire the alert
- **Silencing**: Safe to silence during known Sidekiq maintenance windows or planned deployments. Use Alertmanager silence with matchers `type=ci-orchestration, component=~pipeline_creation_sidekiq.*`
- **Expected frequency**: Rare under normal conditions. Most likely to fire after deployments or during infrastructure incidents affecting Sidekiq

## Severities

Default severity is S3. Consider upgrading to S2 if:

- Pipeline creation is completely stalled (error rate > 50%)
- Multiple worker types affected simultaneously
- Customer reports of pipelines not being created

## Verification

```promql
# Queue duration apdex (5m)
gitlab_component_apdex:ratio_5m{component="pipeline_creation_sidekiq_queue_duration", type="ci-orchestration", environment="gprd"}

# Execution apdex (5m)
gitlab_component_apdex:ratio_5m{component="pipeline_creation_sidekiq_execution", type="ci-orchestration", environment="gprd"}

# Execution error rate (5m)
gitlab_component_errors:ratio_5m{component="pipeline_creation_sidekiq_execution", type="ci-orchestration", environment="gprd"}
```

- [ci-orchestration service overview dashboard](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview) — burn rate panels
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Pipeline Creation section
- [Kibana — Sidekiq CreatePipelineWorker logs](https://log.gprd.gitlab.net/app/discover#/?_g=()&_a=(filters:!((query:(match_phrase:(json.class:'CreatePipelineWorker'))))))

## Recent Changes

- [Production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)
- Rollback: If a recent deploy is suspected, follow the [upgrade and rollback runbook](../../uncategorized/upgrade-and-rollback.md)

## Troubleshooting

### 1. Identify the Affected Worker

Check the [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) "Pipeline Creation" section to see which specific `CreatePipelineWorker` variant is degraded.

### 2. Check Sidekiq Queue Depth

Look at the [Sidekiq Queue Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-queue-detail) for the affected worker's queue. High queue depth with low dequeue rate indicates worker starvation.

### 3. Check for Database Contention

Pipeline creation involves heavy CI table writes. Check:

- [Patroni CI dashboard](https://dashboards.gitlab.net/d/patroni-ci-main) for replication lag
- Database lock contention on `ci_pipelines`, `ci_builds`, `ci_stages` tables

### 4. Check Gitaly Latency

Pipeline creation reads `.gitlab-ci.yml` from Git. Check [Gitaly dashboard](https://dashboards.gitlab.net/d/gitaly-main) for elevated latency.

### 5. Check Recent Deployments

Recent Rails deploys may have introduced regressions in the pipeline creation chain:

- [Production Changes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)

## Possible Resolutions

No past incidents have been recorded yet for this alert. This section will be updated as incidents occur.

## Dependencies

- **Sidekiq**: Worker execution environment
- **PostgreSQL (CI)**: Pipeline and job record creation
- **Gitaly**: `.gitlab-ci.yml` file reads
- **Redis**: Sidekiq job queuing and dequeuing

## Escalation

### When to Escalate

- Alert persists > 1 hour with no improvement
- Error rate > 5% sustained
- Correlated with customer reports of missing pipelines

### Support Channels

- `#s_verify_alerts` (primary)
- `#g_pipeline-authoring` (Pipeline Authoring team)
- `#production` (if S2+ severity)

## Definitions

- [SLI definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/ci-orchestration.jsonnet)
- [Alert rules](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/ci-orchestration/autogenerated-gitlab-gprd-ci-orchestration-service-level-alerts.yml)
- [Edit this runbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/ci-orchestration/alerts/CiOrchestrationServicePipelineCreationSidekiqSLOViolation.md)

## Related Links

- [All ci-orchestration alerts](./)
- [CI pipeline creation runbook](../../ci/pipeline-creation.md): application-level failure modes
  (config fetch timeouts, `config_error` spikes, failure reason reference)
- [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
- [Pipeline processing worker SLO violations](CiOrchestrationServicePipelineProcessingSidekiqSLOViolation.md)
