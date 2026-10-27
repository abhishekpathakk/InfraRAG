# ZoektNodeStorageCritical

## Overview

A Zoekt node's index storage is at or above **85%** used — the
`WATERMARK_LIMIT_CRITICAL` constant
([`ee/app/models/search/zoekt/node.rb:15`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/models/search/zoekt/node.rb#L15))
— and has stayed there for 15 minutes.

Zoekt manages storage with three watermarks, all defined in that same block:

| Constant | Production value | Behaviour |
| --- | --- | --- |
| `WATERMARK_LIMIT_LOW` | 0.60 | Rebalancing begins, to avoid reaching the higher levels |
| `WATERMARK_LIMIT_HIGH` | 0.75 | Storage pressure; rebalancing prioritised |
| `WATERMARK_LIMIT_CRITICAL` | 0.85 | Indexing may be **paused** on the node while namespaces are evicted |

(All three are lower in production than in development, where HIGH is 0.98 and
CRITICAL 0.99 — the alert thresholds use the production branch.)

The consequence that matters: at critical, **indexing on that node can stop**,
so its indices go stale while search continues to serve results from them.
Users get stale code search results without any search error.

## Alert behavior

Fires when `max by (env, environment, zoekt_node_id, zoekt_node_name) (search_zoekt_node_storage_percent_used) >= 0.85` for 15 minutes. The
delay is deliberate — crossing the critical watermark starts evictions
automatically, and a node that dips above the line and self-corrects within a
couple of scheduling cycles is the system working. Fifteen minutes of
sustained critical means eviction is **not** keeping up.

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

Severity **s3**, non-paging, owned by `global_search`.

## First response

Work from cheapest to most disruptive. The
[PVC size must never be increased manually](../README.md#alerts) — Zoekt nodes
are sized with a fixed PVC and it has to stay consistent across the fleet.

1. **Is this one node or the fleet?** Check the storage panel on the
   [observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr).
   If most nodes are above 65%, the answer is capacity, not rebalancing: increase
   replicas by ~20% of total, per
   [when to add a Zoekt node](../README.md#when-to-add-a-zoekt-node).

2. **Check whether evictions are actually running.** Watermark levels are
   visible as `search_zoekt_indices_watermark_levels` (row 4 of the dashboard).
   Indices piling up at `critical` with nothing draining means the rebalancing
   worker is not making progress — check `zoekt.log` and Sidekiq for
   `Search::Zoekt` job failures.

3. **Evict namespaces from the node manually** if rebalancing is stuck:

   ```ruby
   namespace = Namespace.find_by_full_path('some-group')
   enabled_namespace = Search::Zoekt::EnabledNamespace.where(root_namespace_id: namespace.id).first
   enabled_namespace.replicas.delete_all
   ```

   See [evicting namespaces from a Zoekt node](../README.md#evicting-namespaces-from-a-zoekt-node).

4. **Last resort: mark the node as lost**, which removes all namespaces from it
   at once. This is safe — the node re-registers and the architecture
   reallocates — but it triggers reindexing:

   ```ruby
   node_name = 'gitlab-gitlab-zoekt-29'
   Search::Zoekt::Node.by_name(node_name).update_all(uuid: SecureRandom.uuid, last_seen_at: 24.hours.ago)
   ```

   See [marking a zoekt node as lost](../README.md#marking-a-zoekt-node-as-lost).

5. **If indexing pressure is the driver**, pausing indexing fleet-wide buys time
   without losing search:
   `Admin > Settings > Search > Exact code search > Pause indexing`. Pausing is
   preferred over disabling — see
   [pausing Zoekt indexing](../README.md#pausing-zoekt-indexing).

## Sizing context

Worst case, a Zoekt index is about 2.8× the size of the indexed branch's source
(excluding binaries); in practice it is nearer 0.4×. A node crossing critical
shortly after a large namespace lands is usually that namespace being bigger
than the planner's estimate — compare
`search_zoekt_indices_used_storage_bytes` against
`search_zoekt_indices_reserved_storage_bytes` on the dashboard.

## Escalation

Escalate to the Global Search team if evictions are not draining or if the
fleet needs a capacity increase (which is a production change request against
[k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com)).

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)
- Unit tests, including the assertion that this and
  [ZoektNodeStorageHigh](./ZoektNodeStorageHigh.md) are mutually exclusive:
  [`test/mimir-rules/zoekt-alerts_test.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml)

## Related links

- [Exact code search service](../README.md)
- [ZoektNodeStorageHigh](./ZoektNodeStorageHigh.md) — the 75% warning
- [Watermark management](../README.md#watermark-management)
- [`kube_persistent_volume_claim_disk_space`](../README.md#kube_persistent_volume_claim_disk_space) — the PVC-level alert on the same underlying disk
