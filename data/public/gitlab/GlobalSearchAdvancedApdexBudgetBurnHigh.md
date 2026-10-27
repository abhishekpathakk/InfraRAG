# GlobalSearchAdvancedApdexBudgetBurnHigh

## What this alert means

Over the last 6 hours, more than 12.5% of advanced (Elasticsearch) global search
requests missed their apdex target, and the most recent 30 minutes agrees.

That is about **2.5x this path's own baseline spend**. The reference is measured,
not an SLO: across the 28 days before the 2026-09-09 regression the advanced
path's 3-day fail ratio sat at 3.59-4.24%, and its worst single 6-hour window
reached 7.54%. The declared `apdexScore` for the component lives in
`metrics-catalog/services/{api,web}.jsonnet` and governs a wider population;
re-deriving the per-scope targets is tracked separately.

This is the companion to `GlobalSearchAdvancedApdexBurstCountHigh`. That alert
asks *"has the degradation pattern changed?"*; this one asks *"is it costing
enough to matter?"* The two-window structure (6h long, 30m short) follows the
repo's multi-window multi-burn-rate convention, so the alert clears when the
recent rate recovers rather than trailing the long window for hours.

Because the long window keeps integrating, **this alert does not clear when an
individual burst ends** — which is the entire point. A degradation that recovers
between bursts previously paged nothing at all.

## Severity and paging

s3, warning only — it does not page. Owning team: `global_search`
(`#g_global_search`).

Promoting this to s2 would require a `pager: pagerduty` label
(`scripts/validate-alerts` enforces that s1/s2 and only s1/s2 page). That is a
deliberate decision to defer: the burn multiple here is calibrated against a
measured baseline rather than an agreed SLO, so it is not yet a sound basis for
waking someone.

## First response

**Step 1 of [GlobalSearchAdvancedApdexBurstCountHigh](GlobalSearchAdvancedApdexBurstCountHigh.md)
applies here first** — look for a periodic operation on the gprd Advanced Search
cluster (ILM/SLM, force-merge, rebalancing, scheduled reindex) matching the
measured ~4h burst phase. Spend on this path has only ever risen through that
burst train, so the schedule is the first thing to rule out. Then:

1. **Get the current spend and how it compares.**

   ```promql
   1 - avg_over_time(sum(sli_aggregations:gitlab_sli_global_search_apdex_success_total:rate_1h{env="gprd",stage="main",search_type="advanced"})[6h:10m])
     / (avg_over_time(sum(sli_aggregations:gitlab_sli_global_search_apdex_total:rate_1h{env="gprd",stage="main",search_type="advanced"})[6h:10m]) > 0)
   ```

   Baseline: about 5%. Worst pre-regression 6h: 7.5%. At 12.5% you are at 2.5x.

2. **Is `GlobalSearchAdvancedApdexBurstCountHigh` also firing?** Use the pair as
   a diagnostic:

   | Burst count | Budget burn | Reading |
   | --- | --- | --- |
   | firing | firing | Bursts got deeper or longer and it is costing budget. The 2026-09-09 shape. |
   | firing | quiet | The pattern shifted but spend is still near baseline. Watch; likely early. |
   | quiet | firing | Degradation is broad and shallow rather than bursty — suspect a global latency shift or a target mismatch, not a periodic job. |

3. **Split by scope and level** to see whether the spend is concentrated.

   ```promql
   sum by (search_level) (rate(gitlab_sli_global_search_apdex_total{env="gprd",stage="main",search_type="advanced"}[1h]))
     -
   sum by (search_level) (rate(gitlab_sli_global_search_apdex_success_total{env="gprd",stage="main",search_type="advanced"}[1h]))
   ```

   `search_level="global"` degrading far worse than `project` means cross-index
   Elasticsearch queries, which points at cluster-side contention.

4. **Compare against a non-search workload on the same Elasticsearch cluster.**
   If unrelated feature categories degrade in step, the cause is the cluster, and
   the fix is not in search code.

5. **Check whether request volume moved.** Growth in search volume with flat
   per-search latency is a capacity finding, not a defect.

6. Then follow steps 4-6 of
   [GlobalSearchAdvancedApdexBurstCountHigh](GlobalSearchAdvancedApdexBurstCountHigh.md)
   — indexing queues, deploy/flag correlation, cluster health.

## What NOT to do

- **Do not raise the 12.5% multiple to silence a real regression.** If the
  baseline has genuinely moved, re-measure it over a clean 28-day window and
  record the new numbers in the rule's comments.
- **Do not read this as an SLO breach.** It is a burn rate against a measured
  baseline. The component's real SLO is elsewhere and is a separate question.

## No action is a valid outcome

If the spend rose because the apdex *targets* are miscalibrated rather than
because searches got slower, the correct outcome is to fix the targets, not the
cluster. Several advanced scopes share a single 2.452s target derived in 2022;
if the failures sit entirely in scopes on that branch while latency is unchanged,
say so and route it to the target-calibration work.

## Related

- `GlobalSearchAdvancedApdexBurstCountHigh` — same path, burst-time view.
- Zoekt alert rules cover `search_type="zoekt"`; this alert deliberately does
  not.
