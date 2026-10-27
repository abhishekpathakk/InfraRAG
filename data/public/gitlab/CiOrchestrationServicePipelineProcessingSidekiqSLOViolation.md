# Pipeline Processing Sidekiq Worker SLO Violations

Covers:

- `CiOrchestrationServicePipelineProcessingSidekiqQueueingApdexSLOViolation`
- `CiOrchestrationServicePipelineProcessingSidekiqExecutionApdexSLOViolation`
- `CiOrchestrationServicePipelineProcessingSidekiqExecutionErrorSLOViolation`

## Overview

These alerts fire when pipeline processing Sidekiq workers violate their SLO burn rate thresholds, indicating that pipeline state transitions are either slow (apdex) or failing (error rate).

Pipeline processing workers (`Ci::InitialPipelineProcessWorker`, `PipelineProcessWorker`, `Ci::BuildFinishedWorker`, `BuildQueueWorker`) handle the core pipeline state machine: transitioning jobs between states, processing build completions, and queuing the next set of jobs. Degradation here impacts how quickly a pipeline progresses from one stage to the next.

### Impact

- Pipelines appear to "hang" between stages
- Job completion events are delayed (runner finishes but status doesn't update in UI)
- Cascading delays across multi-stage pipelines
- If error rate is elevated: pipeline state transitions silently failing

### Contributing Factors

- Sidekiq concurrency limits being hit (jobs deferred)
- Database contention on CI tables during heavy pipeline activity
- High volume of concurrent pipeline state transitions (e.g., after a mass retry)
- Application errors in pipeline processing logic
- Redis latency affecting Sidekiq job dispatch

## Services

- [ci-orchestration service overview](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview)
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability)
- **Team**: [Verify](https://handbook.gitlab.com/handbook/engineering/devops/verify/)
- **Slack**: `#s_verify_alerts`

## Metrics

### Queue Duration Apdex

Uses `gitlab_sli_sidekiq_queueing_apdex_success_total` / `gitlab_sli_sidekiq_queueing_apdex_total` filtered to `worker=~"Ci::InitialPipelineProcessWorker|PipelineProcessWorker|Ci::BuildFinishedWorker|BuildQueueWorker"`.

- **SLO**: 99% apdex
- **MWMBR fires at**: < 94% (6h window) / < 85.6% (1h window)

### Execution Apdex

Uses `gitlab_sli_sidekiq_execution_apdex_success_total` / `gitlab_sli_sidekiq_execution_apdex_total`.

- **SLO**: 99% apdex
- **MWMBR fires at**: < 94% (6h window) / < 85.6% (1h window)

### Execution Error Rate

Uses `gitlab_sli_sidekiq_execution_error_total` / `gitlab_sli_sidekiq_execution_total`.

- **SLO**: 99.95% success rate (errorRatio: 0.9995)
- **MWMBR fires at**: > 0.3% error rate (6h window) / > 0.72% (1h window)

## Alert Behavior

- Severity: S3 (Slack-only, no paging)
- Routes to: `#s_verify_alerts`
- MWMBR requires both the short window (5m/1h) and long window (30m/6h) to breach simultaneously
- **Silencing**: Safe to silence during known Sidekiq maintenance windows or planned deployments. Use Alertmanager silence with matchers `type=ci-orchestration, component=~pipeline_processing_sidekiq.*`
- **Expected frequency**: Rare under normal conditions. Most likely to fire during database contention or when concurrency limits are hit

## Severities

Default severity is S3. Consider upgrading to S2 if:

- Pipeline processing is completely stalled
- `Ci::BuildFinishedWorker` error rate > 5% (job completions not being processed)
- Multiple worker types affected simultaneously

## Verification

```promql
# Queue duration apdex (5m)
gitlab_component_apdex:ratio_5m{component="pipeline_processing_sidekiq_queueing", type="ci-orchestration", environment="gprd"}

# Execution apdex (5m)
gitlab_component_apdex:ratio_5m{component="pipeline_processing_sidekiq_execution", type="ci-orchestration", environment="gprd"}

# Execution error rate (5m)
gitlab_component_errors:ratio_5m{component="pipeline_processing_sidekiq_execution", type="ci-orchestration", environment="gprd"}

# Concurrency limit deferred jobs (potential cause)
sum by (worker) (rate(sidekiq_concurrency_limit_deferred_jobs_total{worker=~"Ci::InitialPipelineProcessWorker|PipelineProcessWorker|Ci::BuildFinishedWorker|BuildQueueWorker"}[5m]))
```

- [ci-orchestration service overview dashboard](https://dashboards.gitlab.net/d/ci-orchestration-main/ci-orchestration-overview) — burn rate panels
- [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) — Pipeline Processing section
- [Kibana — Sidekiq pipeline processing worker logs](https://log.gprd.gitlab.net/app/discover#/?_g=()&_a=(filters:!((query:(match_phrase:(json.class:'PipelineProcessWorker'))))))

## Recent Changes

- [Production change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)
- Rollback: If a recent deploy is suspected, follow the [upgrade and rollback runbook](../../uncategorized/upgrade-and-rollback.md)

## Troubleshooting

### 1. Identify the Affected Worker

Check the [Pipeline Observability dashboard](https://dashboards.gitlab.net/d/ci-orchestration-pipeline-observability) "Pipeline Processing" section to see which specific worker is degraded.

### 2. Check Concurrency Pressure

Pipeline processing workers have concurrency limits. Check the "Pipeline processing workers concurrency" panel on the Pipeline Observability dashboard. If workers are hitting their limit, jobs are deferred instead of executed.

### 3. Check Database Duration

The "Pipeline processing avg DB duration" panel shows average DB time per worker. If DB duration is elevated (> 5s), the root cause is likely database contention:

- Check [Patroni CI dashboard](https://dashboards.gitlab.net/d/patroni-ci-main) for lock contention and replication lag
- Check for long-running transactions on CI tables

### 4. Check for Mass Retries

A large number of pipeline retries (e.g., from a flaky test suite fix) can cause a sudden spike in processing load. Check `pipelines_created_total` for unusual volume.

### 5. Check Recent Deployments

- [Production Changes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)

## Possible Resolutions

No past incidents have been recorded yet for this alert. This section will be updated as incidents occur.

## Dependencies

- **Sidekiq**: Worker execution environment
- **PostgreSQL (CI)**: Pipeline and job state transitions
- **Redis**: Sidekiq job queuing, dequeuing, and concurrency limit tracking

## Escalation

### When to Escalate

- Alert persists > 1 hour with no improvement
- `Ci::BuildFinishedWorker` failures (critical — job completions not processed)
- Correlated with customer reports of stuck pipelines

### Support Channels

- `#s_verify_alerts` (primary)
- `#g_pipeline-execution` (Pipeline Execution team)
- `#production` (if S2+ severity)

## Definitions

- [SLI definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/ci-orchestration.jsonnet)
- [Alert rules](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/ci-orchestration/autogenerated-gitlab-gprd-ci-orchestration-service-level-alerts.yml)
- [Edit this runbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/ci-orchestration/alerts/CiOrchestrationServicePipelineProcessingSidekiqSLOViolation.md)

## Related Links

- [All ci-orchestration alerts](./)
- [SLO alerting howto](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
- [Pipeline creation worker SLO violations](CiOrchestrationServicePipelineCreationSidekiqSLOViolation.md)
