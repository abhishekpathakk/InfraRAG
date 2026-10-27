# ZoektNodeOfflineWarning

## Overview

A single Zoekt node has stopped sending heartbeats. This is the **early**
node-offline signal; [ZoektNodesOffline](./ZoektNodesOffline.md) is the
one-hour, fleet-level version.

Zoekt nodes self-register and keep themselves online by POSTing to
`/internal/search/zoekt/:uuid/heartbeat`. Three separate timers act on the
absence of that heartbeat, and they matter for interpreting this alert:

| Timer | Value | Effect | Source |
| --- | --- | --- | --- |
| `ONLINE_DURATION_THRESHOLD` | 30s | Rails stops routing search traffic to the node | [`ee/app/models/search/zoekt/node.rb:12`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/models/search/zoekt/node.rb#L12) |
| gitlab-exporter's status query | 2 min | `search_zoekt_nodes_status` drops to 0 | `ZOEKT_NODES_STATUS_QUERY`, [`lib/gitlab_exporter/database/zoekt.rb`](https://gitlab.com/gitlab-org/ruby/gems/gitlab-exporter/-/blob/master/lib/gitlab_exporter/database/zoekt.rb) |
| Lost-node threshold | 10 min in production (12h default) | Indices reallocated to other nodes and reindexed from Gitaly | Admin setting; see [Lost Nodes](../README.md#lost-nodes) |

So by the time this alert fires, search traffic has already been routed away
from the node — user impact starts at 30 seconds, long before the metric moves.

## Alert behavior

Fires when

```promql
avg by (env, environment, zoekt_node_id, zoekt_node_name) (
  search_zoekt_nodes_status{environment="gprd"}
) < 0.5
```

is sustained for 5 minutes — that is, when **more than half** of the duplicate
scrape targets report the node offline.
[ZoektNodesOffline](./ZoektNodesOffline.md) wraps this **identical** inner
predicate in a fleet-level `count(...) > 0` with `for: 1h`, so the two alerts
are two rungs of one ladder and cannot disagree about whether a given node is
offline.

Because the gauge already carries ~2 minutes of built-in delay, this is roughly
**7 minutes of real node downtime** — past a rolling restart, and just before
the 10-minute lost-node threshold triggers reallocation. That window is
deliberate: it is the last point at which bringing the node back avoids a
reindex.

### One alert per node, not twelve — and why it is a MAJORITY vote

The expression aggregates with `avg by (env, environment, zoekt_node_id,
zoekt_node_name) (...) < 0.5`, and that is load-bearing rather than tidy. The
`gitlab-monitor-database-zoekt` scrape job runs on **every gprd patroni host**,
each querying the same Rails database and reporting the same Zoekt fleet, so
`search_zoekt_nodes_status` has **456 series for 38 nodes — 12 duplicate scrape
targets per node** (gstg: 5 per node). Before round 6 of this MR's review, one
affected node therefore produced **twelve identical alerts**.

**The twelve targets are not twelve independent observations.** Each exporter
connects to `host=localhost port=6432`, its own host's pgbouncer, pinned to
`127.0.0.1:5432` — so all twelve read the *same* `zoekt_nodes` row through their
*own local streaming replica*. Target disagreement is therefore replication lag
and scrape skew on one database, and the exporter's predicate makes lag directly
visible: it reports status 0 once `last_seen_at` is older than 2 minutes, while a
healthy node heartbeats every ~5 seconds. **A replica must be more than ~115
seconds behind to report a live node offline.**

That is why the reducer is a majority rather than ANY or ALL. Measured over 30
days on gprd at 5-minute resolution, on the raw predicate:

| semantic | node-steps fired | verdict |
| --- | ---: | --- |
| ANY (`max(status == 0)`) | 334 | **216 of those were one lagging replica** reporting all 36 nodes offline at once |
| ALL (`max(status) == 0`) | 10 | fires at neither of the two fleet-wide stamps; costs 10 of the 20 node-steps a majority agreed on |
| **majority (`avg(status) < 0.5`)** | **90** | fires on every majority-agreed step, on no minority artifact — but 70 of those 90 are database events, not Zoekt events |

On 08-13 at 12:20, 15:35, 15:40 and 15:45 UTC the sole dissenting target was
`patroni-main-v17-04-db-gprd` — 1 of 12 — for every one of 36 nodes
simultaneously. 36 Zoekt nodes do not go offline together and return inside five
minutes.

A 6-6 dead heat across 12 targets gives `avg == 0.5`, which `< 0.5` treats as
**online**: a bare majority is required, not half. 5 node-steps in the 30-day
window landed exactly there, on five distinct nodes, and this rule's `for: 5m`
discards all five.

**What the measurement does not settle, and the correction that matters for
triage.** Scored after the shipped `for:`, ALL and a majority are
indistinguishable over the whole window (2 node-steps each at `for: 5m`, 0 each
at `for: 1h`); only ANY is decisively rejected. And the two stamps at which a
majority of targets agreed the *whole fleet* was offline — 08-21 16:05 and
08-25 09:25 — were **database events with no Zoekt symptom at all**:
`count(zoekt_search_requests_total)` 36 → 36 and `sum(up{type="zoekt"})` 72/72
at both. 08-25 was replication lag (`pg_replication_lag{type="patroni"}` peaking
at 214.9s with eight replicas past the ~115s threshold, and a ninth at 111.6s
just below it); 08-21 was a heartbeat *write*-path stall inside a Rails-wide
outage (max lag only 113.6s, yet seven **zero-lag** replicas reported nodes
offline, and the heartbeat endpoint's request rate fell to 0/s). A majority vote
filters single-replica staleness; it does **not** filter fleet-wide staleness,
because then every target agrees.

So do not read "a majority of `fqdn`s agree" as "this is Zoekt's problem".
[ZoektNodesOffline](./ZoektNodesOffline.md#the-two-30-day-fleet-wide-stamps-were-database-events-not-zoekt-events)
carries the full evidence table and the two discriminating queries; run them
first here too — step 1 below.

**The storage alerts correctly keep `max`**, and the asymmetry is deliberate:
replication lag moves a storage percentage by fractions of a percent, so the
worst reading is the conservative one, but it *flips* a status gauge outright
because that gauge is a threshold comparison against a timestamp.

The duplicates also carry the reporting database host's identity —
`type="patroni"`, `tier="db"`, `service="postgres"`, plus `instance`, `fqdn`,
`shard`, `zone` and `machine_type` — so the alerts grouped under Patroni's own
alerts in Alertmanager (`defaultGroupBy` is
`[env, tier, type, alertname, stage, component]`), sending an on-caller to the
wrong fleet. The aggregation drops those labels and the rule sets
`type: zoekt` / `tier: inf` from `metrics-catalog/services/zoekt.jsonnet` in
their place.

Fixtures whose duplicate targets **disagree** — 2-of-3 offline (fires), 1-of-3
offline (silent), 1-of-12 offline (silent), 10-of-12 offline (fires) — pin this
in the
[unit tests](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml).
Every pre-round-6 fixture used one series per node, and the round-6 fixture gave
all its duplicates the *same value*, which is why the ANY/ALL confusion survived
six rounds of review.

Severity **s4**, non-paging, owned by `global_search`.

## First response

1. **Rule out a stale database row first.** This gauge is a database read, so it
   drops to zero when `zoekt_nodes.last_seen_at` is stale for *any* reason —
   including replication lag and a heartbeat write-path stall, neither of which
   is a Zoekt fault. Two queries settle it:

   ```promql
   # (a) is the fleet serving? unchanged => the SEARCH path is fine
   count(zoekt_search_requests_total{environment="gprd"})
   sum(up{type="zoekt", environment="gprd"})
   ```

   ```promql
   # (b) is the database path stale?
   max(pg_replication_lag{type="patroni", environment="gprd"})
   sum(rate(gitlab_transaction_duration_seconds_count{endpoint_id=~".*zoekt.*heartbeat.*"}[1m]))
   ```

   Zoekt signals flat while (b) is elevated ⇒ database, escalate there, not to
   Global Search. The heartbeat arm is `[1m]` because a stall reads **at or near
   zero** — the 5-minute rate at the 08-21 16:05 stamp still read 1.43/s, inside
   this metric's ordinary 1.8-3.4 req/s band, while the 1-minute rate was 0/s.

   **Zoekt signals flat *and* (b) normal is a different answer: it stays with
   Global Search.** Both arms of (b) are fleet aggregates, so neither can see a
   single node whose heartbeat is not reaching Rails while its pod keeps serving
   and keeps being scraped — one node of ~38 is ~2.6%, well inside the metric's
   own variation. That case is a heartbeat / registration failure (internal
   gateway, internal API, network), not a database event; confirm it against
   Rails, which is authoritative:

   ```ruby
   Search::Zoekt::Node.offline.pluck(:id, :last_seen_at)
   ```

   Note that at the node level a genuine single-node *outage*
   *removes that node* from `up{type="zoekt"}` while leaving the fleet count
   otherwise intact, so compare per node rather than only the total.

2. **Identify the node** from `{{ $labels.zoekt_node_name }}` and check whether
   its pod is healthy:

   ```shell
   kubectl -n gitlab get pod <zoekt_node_name>
   kubectl -n gitlab describe pod <zoekt_node_name> | tail -40
   ```

3. **Check whether this is a deploy.** A StatefulSet rollout restarts nodes one
   at a time; several of these alerts marching through the fleet in sequence,
   each resolving, is a rollout and needs no action. Check the
   [gitlab-com k8s-workloads](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com)
   pipelines.

4. **Check for an OOM.** If the container is restarting rather than gone, look at
   [ZoektContainersRestartsDueToOOM](./ZoektContainersRestartsDueToOOM.md) and
   the Memory row of the
   [zoekt overview dashboard](https://dashboards.gitlab.net/d/zoekt-main/zoekt3a-overview).

5. **Confirm the current state from Rails**, which is authoritative on routing:

   ```ruby
   Search::Zoekt::Node.offline.pluck(:id, :last_seen_at)
   Search::Zoekt::Node.online.count
   ```

6. **Decide whether to let reallocation happen.** If the node is not coming
   back, doing nothing is usually correct — the lost-node mechanism reallocates
   its indices and reindexes from Gitaly, which for GitLab.com's fleet is
   routine. Reindexing a large repository takes ~10-20 seconds. Intervene only
   if a large fraction of the fleet is offline at once, because a mass
   reallocation puts load on Gitaly.

## Safeguard worth knowing

Nodes are **not** marked lost if every node in the cluster is offline. This
prevents a cluster-wide incident from triggering a full reindex. If you see
every node offline, the problem is upstream (network, gateway, internal API),
not the nodes.

## Escalation

If the node cannot be recovered and search quality is visibly degraded,
escalate to the Global Search team. Service owners and escalation paths are in
the [service catalogue](https://gitlab.com/gitlab-com/runbooks/-/tree/master/services).

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)
- Unit tests: [`test/mimir-rules/zoekt-alerts_test.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml)

## Related links

- [Exact code search service](../README.md)
- [ZoektNodesOffline](./ZoektNodesOffline.md)
- [Zoekt observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr)
