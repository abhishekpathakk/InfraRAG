# Removing a slow Sidekiq worker from SLI/SLO alerting

## Overview

Some Sidekiq workers have known performance issues that cause them to exceed
our apdex thresholds. When a worker is consistently slow due to an upstream
bug or design limitation, it can drag down the overall Sidekiq SLI/SLO
measurements, causing noisy alerts that obscure real problems.

Rather than disabling the worker entirely (see [Disabling Sidekiq workers](disabling-a-worker.md)),
you can exclude it from the SLI/SLO calculations while the performance issue
is investigated and fixed. This stops the alerting noise while keeping the
worker running normally.

## When to use this

Use this approach when:

- A specific worker is consistently violating apdex thresholds
- The root cause is a known upstream issue (e.g. a GitLab application bug)
- The worker should continue running, but its poor performance should not
  trigger SLO alerts
- There is a tracking issue for fixing the underlying performance problem

Do **not** use this when:

- The worker is actively causing an incident (use [Disabling Sidekiq workers](disabling-a-worker.md) instead)
- The worker is running normally but the threshold needs adjusting

## How it works

The `ignoredWorkers` list in
[`metrics-catalog/services/sidekiq.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/sidekiq.jsonnet)
defines a negative equality filter (`ne`) on the `worker` label. Workers in
this list are excluded from the `baseSelector` used to compute Sidekiq
SLIs, meaning their execution and queueing metrics will not affect alerting
thresholds.

The worker's metrics are still collected and visible in dashboards — only
the SLI/SLO evaluation ignores them.

## Procedure

### 1. Identify the slow worker

Use the [Sidekiq Worker Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq3a-worker-detail)
to confirm the worker is consistently exceeding apdex thresholds. Note the
full Ruby class name of the worker (e.g. `Search::Zoekt::UpdateIndexUsedStorageBytesEventWorker`).

### 2. Ensure a tracking issue exists

Before excluding the worker, make sure there is an issue tracking the
underlying performance problem. This is important so the exclusion does not
become permanent.

### 3. Add the worker to the ignored list

Edit `metrics-catalog/services/sidekiq.jsonnet` and add the worker class
name to the `ignoredWorkers` list, along with a comment linking to the
tracking issue:

```jsonnet
local ignoredWorkers = { worker: {
  ne: [
    'ProjectExportWorker',  // https://gitlab.com/groups/gitlab-org/-/epics/7940
    'Security::StoreSecurityReportsByProjectWorker',  // https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26967#note_2577951055
    'Search::Zoekt::UpdateIndexUsedStorageBytesEventWorker',  // https://gitlab.com/gitlab-org/gitlab/-/work_items/592620
  ],
} };
```

### 4. Regenerate and verify

Run `make generate` to regenerate the Mimir rules and other derived files,
then verify the output:

```bash
make generate
git diff
```

Review the generated diffs to confirm that only the expected rule files
changed. The diff will typically touch aggregation and alert rule files
under `mimir-rules/` for each tenant (gprd, gstg, pre).

### 5. Submit a merge request

Commit both the Jsonnet source change and the regenerated files. Link the
MR to the incident or tracking issue that motivated the change.

For a real-world example, see
[MR !10221](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/10221)
which temporarily removed `UpdateIndexUsedStorageBytesEventWorker` from
alerting due to [INC-8111](https://app.incident.io/gitlab/incidents/8111).

## Reverting the exclusion

Once the upstream performance issue is fixed, remove the worker from the
`ignoredWorkers` list, run `make generate`, and submit an MR. This restores
the worker to normal SLI/SLO evaluation.
