# ZoektTaskQueueNotDraining

## Overview

A Zoekt node's indexing backlog is **larger than the node can drain inside two
hours**, the deadline the codebase itself sets for a single indexing task. Tasks
in that backlog are therefore breaching the `zoekt_tasks` apdex objective, so the
node's search results are going stale even while search itself stays healthy and
fast.

`{{ $value }}` on this alert is **the backlog, in tasks**.

"Backlog" is precise here. `search_zoekt_task_processing_queue_size` counts
`zoekt_tasks` rows where `perform_at <= now()` and the state is `pending` or
`processing` (`ZOEKT_TASKS_PROCESSING_QUERY` in
[`lib/gitlab_exporter/database/zoekt.rb`](https://gitlab.com/gitlab-org/ruby/gems/gitlab-exporter/-/blob/master/lib/gitlab_exporter/database/zoekt.rb)).
Tasks scheduled for the future are excluded, so a non-zero value is genuinely
work that should already have happened.

## Why this alert has no magnitude threshold

**This is deliberate and it is the interesting part of the rule.**

Zoekt indexing is bursty by design: a push to a large namespace enqueues a lot
of work at once and the queue drains. A threshold like "> 500 tasks" would
therefore fire constantly on healthy burst indexing, and a threshold high enough
not to would have to be invented rather than measured.

So the rule compares the backlog against **what the node can actually complete
in the deadline**, where the deadline is a code constant:

```promql
(
  max by (env, environment, node_id, node_name) (
    min_over_time(search_zoekt_task_processing_queue_size{environment="gprd"}[6h])
  )
  > on(node_id) group_left()
  (
    7200
    *
    (
      sum by (node_id) (label_replace(
        rate(gitlab_sli_search_zoekt_tasks_apdex_total{environment="gprd"}[6h]),
        "node_id", "$1", "zoekt_node", "(.*)"))
      or on(node_id)
      (sum by (node_id) (max by (env, environment, node_id, node_name) (
        min_over_time(search_zoekt_task_processing_queue_size{environment="gprd"}[6h]))) * 0)
    )
  )
)
and on(env, environment, node_id, node_name)
max by (env, environment, node_id, node_name) (
  count_over_time(search_zoekt_task_processing_queue_size{environment="gprd"}[30m] offset 5h30m)
) > 0
```

`7200` is `APDEX_THRESHOLD_S` from
[`ee/lib/gitlab/metrics/zoekt_tasks_slis.rb#L11`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/gitlab/metrics/zoekt_tasks_slis.rb#L11).
`ee/app/services/search/zoekt/callback_service.rb` scores each completed task
with `duration = Time.current - task.perform_at` and
`success: duration <= APDEX_THRESHOLD_S`, so 2h is not a tuned number — it is
the same deadline the `zoekt_tasks` apdex SLI is already measured against
([`metrics-catalog/services/zoekt.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/zoekt.jsonnet)).
A backlog bigger than 2h of the node's own throughput necessarily contains tasks
that will miss it.

The denominator is `gitlab_sli_search_zoekt_tasks_apdex_total`, which increments
once per **completed** task, not `_requests_total`, which increments at
**enqueue** and would measure arrival rather than drain.

### The expression multiplies rather than divides, and that is a correctness fix

The obvious way to write this is `backlog / rate > 7200`. That is what round 6
shipped, and it had **three no-data paths**, two of them silent:

| case | round-6 behaviour |
| --- | --- |
| completion rate present but flat (`rate == 0`) | quotient is `+Inf`, so it fired — and the annotation rendered the literal string **`+Inf`** |
| the node has a queue series and **no** completion counter | the `/ on(node_id) group_left()` join **dropped the node — silent** |
| the node is completing only *failures* | same — **silent** |

The silent cases are the alert's own worst case.
`gitlab_sli_search_zoekt_tasks_apdex_total` is incremented **only on
completion** — inside `task.done!`, while the failure path increments the error
counter instead. **So a node that stops completing tasks stops producing the
denominator**, and after ~6h the rate window empties, the join drops the node,
and **a firing alert resolves with the backlog untouched**. Reproduced against
the round-6 rule file: a backlog pinned at 10,000 with completions stopping at
t=420m fires at +1h and is *gone* at +7h, when the node is strictly worse.

Since `backlog / rate > D` is equivalent to `backlog > D * rate` whenever the
rate is positive, the multiplied form is used instead. It is total where the
quotient is not:

- **rate zero** → the right-hand side is `0`, so the test is `backlog > 0`. That
  is the correct answer rather than a special case: a backlog with no completions
  never drains. No `+Inf` can arise, because nothing is divided.
- **rate series absent** → the `or on(node_id) (... * 0)` arm supplies an
  explicit zero rate for every node that has a queue series, so the join can no
  longer drop a node.
- **`$value`** is the backlog in tasks — finite and actionable — rather than a
  duration that could print as `+Inf`.

**On real data the two forms are indistinguishable**, which is the point: this is
a totality fix, not a sensitivity change. Over 30 days hourly they fire in the
same 700 of 721 gprd hours and 0 of 721 gstg hours, disagree in **zero** hours,
and never fire on different nodes. The false-positive cost of making the stall
case loud is also **zero** on that window: "backlog > 0 with no positive
completion rate" holds in 0 of 721 hours on both tenants, because gstg's
permanently unjoinable node carries a backlog of exactly 0 in all 384 of its
unjoinable hours. An empty queue that is not draining is not an incident, and
the expression says so with no special case.

**As an on-caller, the practical consequence is:** if you see this alert with a
backlog value and the node's completion rate at zero, the node is **stalled**,
not merely slow — go to step 3 of First response before anything else.

### What this replaced, and why

Until round 6 the predicate was simply `min_over_time(queue[6h]) > 0` — "the
queue never reached zero in six hours" — on the theory that a healthy node's
queue always touches zero. **Measured against live gprd, that is false**, and the
rule was continuously satisfied:

| Measurement | Value |
| --- | ---: |
| series matching the old expression, live | **36** (3 nodes x 12 duplicate scrape targets) |
| hours over 30d matching at least one node | **437 / 721 (61%)** |
| paging episodes over 7d honouring `for: 1h` | **6**, longest **59.8h** |

But the three matching nodes were not falling behind. Over 14 days their backlog
was **flat** — `gitlab-gitlab-zoekt-20` went from a first-24h median of 11,566
to a last-24h median of 11,723 — with 19–65% peak-to-trough turnover inside every
6h window. They were busy nodes that never happened to empty, which on a 38-node
fleet is a steady state, not an incident.

The current predicate distinguishes those cases, and the unit tests pin the
distinction with two byte-identical 10,000-task backlogs that differ only in
completion rate: the slow one fires, the fast one does not.

Measured over the same 30d hourly grid:

| expression | hours matching | simultaneous alert instances |
| --- | ---: | ---: |
| old `min_over_time(q[6h]) > 0` | 437 / 721 (61%) | median **36**, max 60 |
| current backlog-vs-throughput form | 700 / 721 (97%) | median **1**, max 2 |

The new form is *more* often true and **36x quieter**, because it has isolated a
single real problem instead of flagging three healthy nodes: 700 of those 721
node-hours are `gitlab-gitlab-zoekt-20`, whose 7-day `zoekt_tasks` apdex is
**0.518%** over 717,736 completions.

### That means this alert fires on deploy, and that is intended

`ZoektServiceZoektTasksApdexSLOViolation`, generated by the metrics-catalog
framework from the same SLI, has **already been firing on gprd for 712 of the
last 719 hours** on both its 1h and 6h windows. Fleet-wide 7-day task apdex is
92.05%, and `gitlab_component_apdex:ratio_1h{component="zoekt_tasks"}` was below
its 0.999 objective in **720 of 720** hours. So this rule adds no new noise to a
channel that is already being told about the problem.

What it adds is the one thing the SLO alert structurally cannot say: **which
node**. The firing SLO alert's label set contains no node label at all. The
underlying capacity question on `gitlab-gitlab-zoekt-20` is a Global Search
product question, not an alerting bug.

The threshold is deliberately **not** raised to make the alert quiet — that is
the move the 1800 -> 3600 -> 7200 history on the `zoekt_tasks` apdex threshold
already made twice.

**And if `APDEX_THRESHOLD_S` is raised again, this alert goes nearly silent
without anyone touching this repository.** The coupling is intentional — the rule
means "tasks will breach the SLI's own deadline", so it must move when the SLI
moves — but the sensitivity is a cliff. Holding the expression and moving only
the constant, measured 30d hourly on gprd:

| deadline | hours of 721 the rule fires |
| --- | ---: |
| 1800 (original) | 719 (100%) |
| 3600 (intermediate) | 719 (100%) |
| **7200 (current)** | **700 (97%)** |
| 14400 (one more doubling) | **12 (2%)** |
| 28800 | 3 (0%) |

The fleet's drain-time distribution sits *just* over the 2h line (p10 2.21h,
p50 2.78h, p90 3.55h), which is why one doubling takes it from 97% to 2%.

### Why the aggregation is load-bearing

`max by (env, environment, node_id, node_name)` is not tidying. The
`gitlab-monitor-database-zoekt` scrape job runs on **every gprd patroni host**,
and each host queries the same Rails database and reports the same Zoekt fleet,
so every `search_zoekt_*` series exists **12 times per node** (456 series for 38
nodes; gstg has 5 per node). Unaggregated, one backed-up node produced twelve
identical alerts, and they inherited the reporting database host's identity —
`type="patroni"`, `tier="db"`, `service="postgres"` — so they grouped under
Patroni's own alerts. The rules now set `type: zoekt` / `tier: inf` from
`metrics-catalog/services/zoekt.jsonnet`.

`max` is the right reducer here for the same reason it is right on the storage
gauges and *wrong* on the node-status gauge: the twelve duplicates read the same
Rails table through their own local Postgres replicas, so their disagreement is
replication lag. On a queue *depth* that shifts the value by a few seconds of
enqueues, and the worst reading is the conservative one. On the boolean
`search_zoekt_nodes_status` gauge the same lag flips the value outright, which is
why the two node-offline alerts use a majority vote instead — see
[ZoektNodesOffline](./ZoektNodesOffline.md).

### Why the staleness gate is a series-age test, not a sample count

`min_over_time` returns the minimum of **whatever samples exist** — it does not
require a full window. Without a staleness gate, a series only 70 minutes old
with a genuine backlog satisfies a 6h expression, and the annotation then asserts
six hours of evidence that was never measured. That is not hypothetical: the
series is keyed by `node_id` = `zoekt_nodes.id`, and both fleet scale-up and
lost-node replacement mint fresh series (the lost-node threshold is 10 minutes,
and a rejoining lost node is wiped).

Until round 6 the gate was a **sample count**, `count_over_time(...[6h]) >= 600`,
derived from 6h / 30s = 720 minus headroom. A sample count is a poor proxy for
series age, because it also drops on scrape loss — and gprd's scrape loss is
large, diurnal and permanent. Measured over 30 days at hourly resolution, median
across all 456 gprd series:

```promql
count_over_time(search_zoekt_task_processing_queue_size{environment="gprd"}[6h])
# 30d hourly: min 216  median 628  max 719
#   below 600 (the old floor) in 315 of 721 hours (44%)
count_over_time(search_zoekt_task_processing_queue_size{environment="gprd"}[1h])
# 120 == full 30s coverage.  median 106  =>  ~12% scrape loss
#   p90 loss 37%
# The two figures above are the median ACROSS SERIES per hour, summarised over
# the 721 hours. The WORST hour of that same median-across-series quantity is
# 97.5%; the worst single SERIES-hour, a different statistic, lost 99.2%.
# Three statistics, named so they are not read as comparable. (An earlier
# revision of this block said 98% and 82%; both were wrong — see B15. All
# figures are on an hour-aligned 30d grid. An unaligned `now-30d` grid is not
# reproducible at the tail — the final bucket is partial, and re-running the
# same quantity at seven end offsets inside one hour moved both figures by
# roughly 15 percentage points; the interval itself is not stable between runs
# (two independent seven-offset sweeps gave different floors and ceilings), so
# no interval is quoted. Use the hour-aligned figures.)
```

Consequence: the 600 floor **silenced a live symptom in 339 of 721 hours (47%)**,
284 of them completely. It was suppressing the fleet, not young series.

The replacement asks the question directly: *did this series produce at least one
sample in the oldest 30 minutes of the 6h window?* A 30-minute bucket holds ~60
samples at 30s cadence so it survives heavy loss, while a series younger than
5h30m has no sample there at all. Measured on the same 30d grid:

| gate | symptomatic hours where it suppressed a live series |
| --- | ---: |
| `count_over_time(...[6h]) >= 600` (old) | **339 / 721 (47%)** |
| `count_over_time(...[30m] offset 5h30m) > 0` (current) | **2 / 721 (0.3%)** |

And it still does its actual job: it rejected 24 genuinely fresh series for six
consecutive hours on 09-04, and 432 on 08-18. In **0 of 721 hours** did the old
floor admit a series the age test rejects, so the age test is strictly the more
conservative of the two on the property the gate exists for.

### A magnitude threshold is no longer needed

The round-3..5 versions of this runbook asked for a magnitude threshold to be
added once a baseline existed, because the shape-only predicate could not catch a
fast-growing queue that still touched zero between bursts. The
backlog-vs-throughput form covers that case without a baseline: a queue growing
faster than it drains exceeds its own throughput budget regardless of absolute
depth.

## Alert behavior

Fires when the 6h-minimum backlog exceeds two hours of the node's own 6h
completion throughput **and** the series is older than the 6h window, sustained
one hour. A node created in the last six hours never fires. **A node that has
stopped completing tasks entirely fires on any non-empty backlog** — its
throughput is zero, so nothing drains — and it keeps firing rather than falling
silent when its completion counter disappears. Severity **s4**,
`user_impacting: no`, and there is no `pager: pagerduty` label — it routes to
`#g_global_search_alerts` via the `team: global_search` matcher, so it does not
page.

## First response

1. **Check whether indexing is paused.** This is the most common benign cause
   and the cheapest to rule out:
   `Admin > Settings > Search > Exact code search > Pause indexing`. Indexing
   may have been paused deliberately during an incident or maintenance — see
   [pausing Zoekt indexing](../README.md#pausing-zoekt-indexing).

2. **Check whether the node is at the critical watermark.** At 85% storage,
   indexing on a node **is paused by design** while namespaces are evicted, so a
   stuck queue is a symptom, not the problem. Fix the storage first:
   [ZoektNodeStorageCritical](./ZoektNodeStorageCritical.md).

3. **Get the task-state breakdown.** The state tells you where it is stuck:
   - piling up in `pending` — the node is not pulling tasks (it pulls every 5s
     by default, `TASK_PULL_FREQUENCY_DEFAULT`)
   - piling up in `processing` — the node is pulling but not finishing
   - growth in `failed` / `orphaned` — tasks are erroring; check the indexing
     SLI error rate, which has its own autogenerated SLO alert
     (`ZoektServiceZoektTasksErrorSLOViolation`)

   **Use `rake gitlab:zoekt:info` (step 6) for this today.** The
   `search_zoekt_node_tasks{state}` panel in row 3 of the
   [observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr)
   is the intended source, but that metric was only added in gitlab-exporter
   16.9.0 and chef-repo pins `gitlab_exporter_version` to `16.8.0` for both
   gprd and gstg, so the panel is **empty in production** — as is the
   `search_zoekt_indices_with_stale_used_storage_bytes` panel in row 5. Only
   once that pin is raised does the dashboard answer this step. The queue-size
   panel this alert fires on (`search_zoekt_task_processing_queue_size`) does
   report on 16.8.0, so it tells you *which node* is stuck but not *which
   state*.

4. **Check the node's own health.** Indexer CPU is capped by `GOMAXPROCS` (20 in
   production) and concurrency by the indexing CPU-to-tasks multiplier. A
   throttled or OOM-restarting indexer container cannot drain a queue — CPU and
   Memory rows of the
   [zoekt overview dashboard](https://dashboards.gitlab.net/d/zoekt-main/zoekt3a-overview).

5. **Check Sidekiq.** Task creation and callbacks run through Sidekiq; dropped or
   failing `Search::Zoekt` jobs stall the pipeline. Look for
   `drop_sidekiq_jobs_Search::Zoekt::*` feature flags being set — the rollout
   worker in particular can be disabled deliberately:

   ```
   /chatops gitlab run feature get drop_sidekiq_jobs_Search::Zoekt::RolloutWorker
   ```

6. **Get the authoritative picture from Rails**, which is more detailed than any
   metric:

   ```shell
   rake gitlab:zoekt:info
   ```

   or with auto-refresh: `rake "gitlab:zoekt:info[60]"`. See
   [monitoring Zoekt system state](../README.md#monitoring-zoekt-system-state).

## Escalation

Escalate to the Global Search team. This is not user-impacting in the immediate
sense, so it does not warrant paging — but a queue that never drains means code
search results are silently going stale, which users experience as "search
can't find my code" rather than as an outage. Do not let it sit indefinitely.

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)
- Unit tests, including the draining-queue negative control:
  [`test/mimir-rules/zoekt-alerts_test.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml)

## Related links

- [Exact code search service](../README.md)
- [Indexing flow](../README.md#indexing-flow)
- [Reindexing from scratch](../README.md#reindexing-from-scratch) — expected
  timelines, for distinguishing a stuck queue from a legitimate reindex
- [ZoektNodeStorageCritical](./ZoektNodeStorageCritical.md)
