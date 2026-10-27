# ZoektNodeStorageHigh

## Overview

A Zoekt node's index storage has been at or above **75%** used for an hour —
the `WATERMARK_LIMIT_HIGH` constant
([`ee/app/models/search/zoekt/node.rb:14`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/models/search/zoekt/node.rb#L14)).

This is a **capacity-planning** signal, not an incident. At the high watermark
the node is under storage pressure and rebalancing is prioritised for it, but
indexing continues normally. The alert exists to catch the fleet trending
towards the critical watermark, where indexing does stop —
see [ZoektNodeStorageCritical](./ZoektNodeStorageCritical.md).

## Alert behavior

Fires when the per-node maximum storage used is in `[0.75, 0.85)` for one hour. The expression is
bounded above deliberately, so this and `ZoektNodeStorageCritical` are mutually
exclusive: a node above 85% pages the critical alert only, and does not also
produce this one. That exclusion is asserted in the
[unit tests](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml).

The one-hour `for` reflects what the level means: HIGH is about prioritisation,
so a node that briefly touches it is uninteresting and a node that settles
there is the actual signal.

### One alert per node, not twelve

The expression aggregates with `max by (env, environment, zoekt_node_id,
zoekt_node_name)`, and that is load-bearing rather than tidy. The
`gitlab-monitor-database-zoekt` scrape job runs on **every gprd patroni host**,
each querying the same Rails database and reporting the same Zoekt fleet, so
`search_zoekt_node_storage_percent_used` has **456 series for 38 nodes — 12 duplicate scrape
targets per node** (gstg: 5 per node). Before round 6 of this MR's review, one
affected node therefore produced **twelve identical alerts**.

The duplicates also carry the reporting database host's identity —
`type="patroni"`, `tier="db"`, `service="postgres"`, plus `instance`, `fqdn`,
`shard`, `zone` and `machine_type` — so the alerts grouped under Patroni's own
alerts in Alertmanager (`defaultGroupBy` is
`[env, tier, type, alertname, stage, component]`), sending an on-caller to the
wrong fleet. The aggregation drops those labels and the rule sets
`type: zoekt` / `tier: inf` from `metrics-catalog/services/zoekt.jsonnet` in
their place.

A fixture with three duplicate targets per node pins this in the
[unit tests](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml);
every pre-round-6 fixture used one series per node, which is why five rounds of
review did not see it. The duplicates in that fixture deliberately **disagree**
(0.90 / 0.91 / 0.92), which is what makes the choice of reducer visible: `max`
shows the on-caller the worst reading rather than an arbitrary one.

**Why this alert uses `max` where the node-offline alerts use a majority vote.**
The twelve targets all read the same Rails row through their own host's local
Postgres replica, so their disagreement is replication lag. On a *continuous*
gauge like storage-percent that shifts the value by whatever the disk moved in a
few seconds — fractions of a percent — so the worst reading is the conservative
one and `max` is correct. On the *boolean* `search_zoekt_nodes_status` gauge the
same lag flips the value outright, because that gauge is a threshold comparison
against a timestamp; `max` there would let one stale replica veto a real alert.
See [ZoektNodesOffline](./ZoektNodesOffline.md) for the measurement. The
asymmetry is deliberate, not drift.

Severity **s4**, non-paging, `user_impacting: no`.

## First response

This alert usually needs a decision, not an intervention.

1. **Look at the whole fleet, not the alerting node.** On the
   [observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr),
   the storage panel draws all three watermarks. The documented trigger for
   adding capacity is **all nodes above 65% disk utilization**, at which point
   increase replicas by 20% of total (22 nodes → add 4) —
   [when to add a Zoekt node](../README.md#when-to-add-a-zoekt-node).

2. **If it is one node**, rebalancing should relieve it. Confirm it is working
   rather than waiting: watch `search_zoekt_indices_watermark_levels` and the
   node's storage trend over a few hours. A flat line at 0.8 for a day means
   rebalancing has nowhere to move the data to, i.e. the fleet is full.

3. **Check unclaimed storage across the fleet** (dashboard row 2). This is
   usable storage minus storage already reserved by indices, so it is the
   headroom the planner has left. Fleet-wide unclaimed storage trending to zero
   is the leading indicator for a capacity request.

4. **No action is a valid outcome.** If the fleet has headroom and rebalancing
   is running, record that and let the alert resolve.

## Escalation

Not a paging alert. If a capacity increase is warranted, that is a production
change request raising `replicas` in
[k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/gprd.yaml.gotmpl),
coordinated with the Global Search team.

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)

## Related links

- [Exact code search service](../README.md)
- [ZoektNodeStorageCritical](./ZoektNodeStorageCritical.md) — the 85% alert
- [Watermark management](../README.md#watermark-management)
- [Scalability: how much Zoekt storage do we need](../README.md#how-much-zoekt-storage-do-we-need)
