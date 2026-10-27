# GlobalSearchAdvancedApdexBurstCountHigh

## What this alert means

The advanced (Elasticsearch) global search path has spent more than 30 minutes of
the last 6 hours with over 40% of searches missing their apdex target.

It is a **burst-count** alert, not a threshold alert. The value it reports is a
count of 5-minute samples, not a ratio. A count of 6 means 30 minutes; 12 means
an hour.

This shape exists because a sustained-threshold alert cannot see this SLI's real
failure mode. Advanced search apdex on gprd is normally sawtoothed: it degrades
in bursts and recovers to 99%+ in between. A `threshold` + `for:` rule therefore
evaluates healthy for most of every hour even while the error budget drains. The
2026-09-09 regression ran about two days with no page and no incident.

**So do not judge this alert by the apdex value you see when you open the
dashboard.** Between bursts the path looks fine. That is the normal state and it
is not evidence the problem is over.

## Severity and paging

s3, warning only — it does not page. The signal is a shift in a periodic
pattern, which needs a human to look within a working day, not at 03:00. Owning
team: `global_search` (`#g_global_search`).

## First response

**Start with the Elasticsearch cluster's periodic operations.** This alert has
only ever fired on a clock-locked burst train, so the first question is what runs
on a schedule, not what changed in Rails.

1. **Look for a periodic operation on the gprd Advanced Search cluster.** Check
   ILM and snapshot (SLM) policy execution, force-merges, shard rebalancing and
   any scheduled batch reindex, and line their schedules up against the burst
   phase below. Measured on gprd over the 28 days to 2026-09-09 15:35Z, bursts
   arrive phase-locked to a **4-hour** period (Rayleigh R=0.86 against a 0.09
   uniform-noise floor for the same sample count), with a mean offset near the
   top of the hour. After the 2026-09-09 onset the 4-hour lock decays to R=0.27
   while a 2-hour lock persists at R=0.51 — i.e. the train gained a cycle rather
   than shifting. A schedule that matches that period is the prime suspect; an
   unscheduled cause almost never produces a lock this tight.

   Cluster view access is required. If you do not have it, escalate to the team
   that owns the cluster rather than continuing down this list — "what runs every
   ~4h on this cluster, and what changed about it on 2026-09-09" is still an open
   question in
   [gitlab-org/gitlab#628744](https://gitlab.com/gitlab-org/gitlab/-/issues/628744).

2. **Confirm the shape, not the level.** Open the [Global Search stage group
   dashboard](https://dashboards.gitlab.net/d/stage-groups-global_search/stage-groups-group-dashboard-enablement-global-search)
   at a 6-hour zoom. You are looking for whether the bursts got *longer, deeper,
   or more frequent* — not for a flat line above a threshold.

   ```promql
   1 - sum(sli_aggregations:gitlab_sli_global_search_apdex_success_total:rate_5m{env="gprd",stage="main",search_type="advanced"})
     / (sum(sli_aggregations:gitlab_sli_global_search_apdex_total:rate_5m{env="gprd",stage="main",search_type="advanced"}) > 0)
   ```

   Baseline for comparison, measured 2026-09-11 over the 28 days to
   2026-09-09 15:35Z: 6.5 bursts/day, 25-55 minutes each, in-burst peak 21-48%,
   and never more than 2 samples above 40% in any 6h window.

3. **Is it only the advanced path?** Compare the other search types. If `zoekt`
   and `basic` are flat while `advanced` moves, the problem is Elasticsearch-side
   rather than in Rails or in search generally.

   ```promql
   sum by (search_type) (rate(gitlab_sli_global_search_apdex_total{env="gprd",stage="main"}[5m]))
   ```

4. **Check indexing.** A large or stalled indexing queue contends with search on
   the same cluster. `gitlab_search_initial_indexing_queue_backing_up` and
   `gitlab_search_incremental_indexing_queue_backing_up` cover the queues
   directly; if either is also firing, treat indexing as the likelier cause.

5. **Rule out a deploy or flag flip** by lining the onset up against
   [gitlab-com/gl-infra/feature-flag-log](https://gitlab.com/gitlab-com/gl-infra/feature-flag-log)
   and the deploy timeline. A burst-shape change that starts on a clean 5-minute
   boundary with no deploy nearby is more likely cluster-side.

6. **Check Elasticsearch cluster health** — node count, CPU, JVM heap, and hot
   threads. The 2026-09-09 regression coincided with growth in Elasticsearch
   query volume and reproduced on non-search feature categories using the same
   cluster, which is the signature of cluster-side contention rather than a
   search bug.

## What NOT to do

- **Do not silence this by widening the gate or raising the count.** Both numbers
  are derived from the measured pre-regression baseline (see the comments in
  `libsonnet/alerts/global-search-advanced-apdex-alerts.libsonnet`). If the
  baseline genuinely moved, re-measure it and say so in the change.
- **Do not resolve it because apdex currently reads 99%.** See above; that is
  the between-burst state.

## No action is a valid outcome

If the burst count rose because search volume grew and latency per search did
not, that is capacity, not a defect. Record the finding and route it to capacity
planning rather than closing silently.

## Related

- `GlobalSearchAdvancedApdexBudgetBurnHigh` — the same path, measured by budget
  spend rather than burst time. Both firing means a deep, sustained degradation.
  Burst-count alone means the pattern shifted without much budget cost yet.
- Zoekt has its own alert rules; this alert deliberately does not cover
  `search_type="zoekt"`.
