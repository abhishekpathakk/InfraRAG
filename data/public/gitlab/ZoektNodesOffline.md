# ZoektNodesOffline

## Overview

One or more Zoekt nodes have been offline for over an hour. Unlike
[ZoektNodeOfflineWarning](./ZoektNodeOfflineWarning.md), which is the early
per-node signal, this one means the self-healing mechanism has already had its
chance: the lost-node threshold (10 minutes in production) will have
reallocated the node's indices long before an hour elapsed, so a node still
reported offline at this point is not coming back on its own.

Offline nodes serve no search traffic. Searches for namespaces that were
assigned to them fall back to Advanced Search, or to Basic Search if Advanced
Search is unavailable — so code search results are degraded rather than absent.

## Alert behavior

Fires when

```promql
count by (env, environment) (
  avg by (env, environment, zoekt_node_id, zoekt_node_name) (
    search_zoekt_nodes_status{environment="gprd"}
  ) < 0.5
) > 0
```

is sustained for one hour. `{{ $value }}` in the alert is the **number of
offline nodes**, not a node name — this is a fleet-level count, so use the
[dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr)
or Rails to find which nodes.

[ZoektNodeOfflineWarning](./ZoektNodeOfflineWarning.md) uses the **identical
inner predicate** with `for: 5m` instead of `for: 1h`. The two alerts differ
only in how long the condition must hold, so they cannot disagree about whether
a given node is offline — which they could, and did, before round 7.

### Why the inner aggregation is a MAJORITY, not `max`

`search_zoekt_nodes_status` is emitted by the `gitlab-monitor-database-zoekt`
scrape job, which runs on **every gprd patroni host** — each one queries the same
Rails database and reports the same Zoekt fleet — so the metric has **456 series
for 38 nodes, exactly 12 duplicate scrape targets per node**.

A bare `count by (environment)` counts *series*, so with one node genuinely
offline the annotation rendered:

> **12 Zoekt node(s) have been offline** for more than 1 hour.

That was fixed in round 6 by collapsing the duplicates first. If you are reading
an alert from before that fix landed, divide by 12 on gprd (5 on gstg).

Round 6 collapsed them with `max by (...) (status == 0)`, which counts a node
offline if **any one** of the twelve targets says so. Round 7 replaced that,
because **the twelve targets are not twelve independent observations**: each
exporter reads the same `zoekt_nodes` row through its own host's local streaming
replica (`host=localhost port=6432` → `127.0.0.1:5432`), so disagreement between
them is replication lag, not twelve opinions about the node. Since the exporter
reports status 0 once `last_seen_at` is older than 2 minutes and a healthy node
heartbeats every ~5 seconds, a replica must be **more than ~115 seconds behind**
to report a live node offline.

Measured over 30 days on gprd at 5-minute resolution, on the raw predicate
(before `for:` is applied):

| semantic | node-steps fired | verdict |
| --- | ---: | --- |
| ANY (`max(status == 0)`) | 334 | **216 of those were one lagging replica** reporting all 36 nodes offline at once |
| ALL (`max(status) == 0`) | 10 | fires at neither of the two fleet-wide stamps below; costs 10 of the 20 node-steps a majority agreed on |
| **majority (`avg(status) < 0.5`)** | **90** | fires on every majority-agreed step, on no minority artifact — but 70 of those 90 are the two database events below |

A 6-6 dead heat across 12 targets gives `avg == 0.5`, which `< 0.5` treats as
**online** — a bare majority is required, not half. That happened at 5
node-steps in the 30-day window, on five distinct nodes; `for: 5m` discards all
five.

**What the measurement does not settle.** Scored the way you actually
experience it, *after* `for:`, the three semantics over the same 30 days are:

| semantic | `for: 5m` (the warning) | `for: 1h` (this alert) |
| --- | ---: | ---: |
| ANY | 72 node-steps (68 of them the 08-13 replica-lag stamps) | 0 |
| ALL | 2 | 0 |
| majority | 2 | 0 |

So the data decisively rejects ANY and is **indistinguishable between ALL and
a majority**. The majority is used because it degrades gracefully — a real
single-node outage is visible to 7 of 12 targets long before all 12 agree — but
whether Global Search prefers ALL for the s3 rung is an open question, not one
this window answers.

### The two 30-day fleet-wide stamps were DATABASE events, not Zoekt events

This is the most important thing on this page for triage. The two stamps at
which a majority of targets agreed the whole fleet was offline —
**08-21 16:05** and **08-25 09:25** — had *no Zoekt-side symptom whatsoever*.
At both, `count(zoekt_search_requests_total)` was 36 → 36, `sum(up{type="zoekt"})`
was 72/72, and the search rate held at 7.8-8.4 req/s. Their causes were
different from each other and both were in the database path:

| stamp | cause | evidence |
| --- | --- | --- |
| 08-25 09:25 | **replication lag** | `pg_replication_lag{type="patroni"}` 0.04s → 214.9s → 0.08s inside ten minutes, with **eight** replicas simultaneously past the ~115s staleness threshold (v17-09 214.9s, -10 168.9s, -11 165.1s, -05 157.2s, -06 157.1s, -03 148.9s, -04 140.8s, -08 125.8s) and a ninth at 111.6s just below it (-07, which reported only **6** nodes offline against the others' 36). The three replicas at ~0s lag reported nothing offline. |
| 08-21 16:05 | **heartbeat write-path stall**, *not* lag | Max lag peaked at 113.6s — below the threshold — on only 4 hosts, yet **seven zero-lag replicas** reported 33-36 nodes offline. A zero-lag replica sees the primary's current row, so the primary's `last_seen_at` genuinely was stale. The heartbeat endpoint's request rate fell 2.6/s → 0/s at 16:04-16:05, inside a Rails-wide outage (all Rails transactions 5.1e4/s → 3.8e3/s, request errors 1.6/s → 608/s). |

**A majority vote filters *single-replica* staleness. It does not filter
*fleet-wide* staleness**, from either cause, because in that case every target
agrees. So the number of dissenting `fqdn`s is **not** the discriminator
between "database problem" and "Zoekt problem" — see First response step 1.

The rule also sets `type: zoekt` / `tier: inf` explicitly, because the
exporter-sourced series carry the *reporting database host's* identity —
`type="patroni"`, `tier="db"`, `service="postgres"` — and without an override
these alerts grouped under Patroni's own alerts in Alertmanager, sending an
on-caller to the wrong fleet.

Severity **s3**, non-paging, owned by `global_search`.

## First response

1. **First, establish which failure path this is.**
   `search_zoekt_nodes_status` is a database read, so it goes to zero when the
   `zoekt_nodes` row is stale — and the row goes stale for four different
   reasons: the nodes are genuinely down; the nodes are healthy but their
   *heartbeat* is not reaching Rails; replication is behind; or the heartbeat
   writes stalled server-side. Only the last two belong to the database team;
   the first two are Global Search's. Twice in the last 30 days this alert's
   condition was met while every Zoekt node was serving searches normally —
   **but both of those were fleet-wide events, and a single-node firing of this
   alert has no such precedent in the window.** Run **both** of these before
   anything else:

   ```promql
   # (a) Is the Zoekt fleet actually serving? Flat/unchanged => the SEARCH path is fine.
   count(zoekt_search_requests_total{environment="gprd"})
   sum(up{type="zoekt", environment="gprd"})
   sum(rate(zoekt_search_requests_total{environment="gprd"}[5m]))
   ```

   ```promql
   # (b) Is the database path stale? Either arm being elevated explains the alert.
   max(pg_replication_lag{type="patroni", environment="gprd"})
   pg_replication_lag{type="patroni", environment="gprd"} > 30
   sum(rate(gitlab_transaction_duration_seconds_count{endpoint_id=~".*zoekt.*heartbeat.*"}[1m]))
   ```

   The heartbeat arm uses `[1m]` deliberately. A stall reads **at or near zero**
   — at the 08-21 16:05 stamp in the evidence table above the 1-minute rate was
   **0/s** against a quiet-day band of 1.8-3.4 req/s, while the 5-minute rate at
   the same instant still read **1.43/s**, which is merely low and is inside the
   range this metric wanders through on an ordinary day. Judge it by magnitude,
   not by adjective: near-zero is a stall, a 40% dip is not.

   Interpretation:

   | (a) Zoekt signals | (b) lag / heartbeat rate | Reading |
   | --- | --- | --- |
   | unchanged | lag elevated, or heartbeat rate at/near zero | **Database, not Zoekt.** Escalate to the database team. This alert is reporting a stale row. |
   | unchanged | **both normal** | **NOT a database event — stay with Global Search.** A stale `last_seen_at` with a healthy database *and* a healthy scrape target is a **heartbeat / registration failure**: the node is serving searches but its heartbeat is not reaching Rails, so Rails has marked it offline and stopped routing to it. Go to step 3 (internal gateway, internal API, network), and confirm against Rails first — see below. |
   | nodes missing from `up` / `count` dropped | normal | **Genuine Zoekt outage.** Continue below. |
   | nodes missing | lag also elevated | Both. Treat the Zoekt outage as real and mention the lag. |

   **"(b) normal" does not mean "the database is fine for this node".** Both
   arms of (b) are **fleet aggregates**: `max(pg_replication_lag)` is over all
   patroni hosts, and the heartbeat rate is summed over the whole fleet, so one
   node of ~38 is ~2.6% of it — an order of magnitude below the metric's own
   ordinary variation (measured at 1.8-3.4 req/s across two quiet control
   windows). Neither query can detect a **single-node** heartbeat failure, which
   is the common shape of this alert. When (a) is unchanged and (b) is normal,
   the aggregate has told you nothing about the individual node; ask Rails,
   which is authoritative (the same query as step 2):

   ```ruby
   Search::Zoekt::Node.offline.pluck(:id, :last_seen_at)
   ```

   The per-target spread is still worth a look, but only as corroboration — a
   *minority* of dissenting hosts is definitely a replica artifact, while a
   majority is **not** evidence that Zoekt is at fault:

   ```promql
   count by (fqdn) (search_zoekt_nodes_status{environment="gprd"} == 0)
   ```

2. **Count them, and compare against the fleet size.** Production runs 38
   replicas ([gprd values](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/gprd.yaml.gotmpl)).
   One node offline out of 38 is a capacity nuisance; ten is an incident.

   ```ruby
   Search::Zoekt::Node.offline.pluck(:id, :last_seen_at)
   Search::Zoekt::Node.count
   ```

3. **Check whether the whole cluster is offline.** If it is, nodes are *not*
   being marked lost — that safeguard exists to prevent a mass reindex — and the
   fault is upstream of the nodes: the internal gateway, the internal API, or
   the network. Fix that, not the nodes. (Note this is also the shape a
   fleet-wide database staleness event takes, so step 1 comes first.) **This is
   also where step 1's "(a) unchanged, (b) both normal" row lands**, at any
   scale: a node that serves searches while its heartbeat does not reach Rails
   has a fault on this path, not in the database.

4. **Check the StatefulSet.** A node stuck in `Pending` is usually a scheduling
   or PVC problem, not a Zoekt problem:

   ```shell
   kubectl -n gitlab get statefulset gitlab-gitlab-zoekt
   kubectl -n gitlab get pods -l app=gitlab-zoekt --field-selector=status.phase!=Running
   ```

   Nodes are pinned to `gitlab.com/node-type: generic-mem` and request 128Gi of
   memory for the webserver, so a node-pool shortage shows up here.

5. **Check remaining capacity.** With nodes gone, the surviving nodes absorb
   their namespaces. Look at storage and unclaimed storage on the
   [observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr)
   — if the fleet is heading for the watermarks, see
   [ZoektNodeStorageHigh](./ZoektNodeStorageHigh.md) and
   [when to add a Zoekt node](../README.md#when-to-add-a-zoekt-node).

6. **If a node is wedged with data on it that will not come back**, mark it lost
   explicitly so reallocation proceeds:

   ```ruby
   node_name = 'gitlab-gitlab-zoekt-29'
   Search::Zoekt::Node.by_name(node_name).update_all(uuid: SecureRandom.uuid, last_seen_at: 24.hours.ago)
   ```

   The new UUID must not already exist in the table. The node re-registers as a
   new node when it returns and is wiped.

### Why the alert is not gated on replication lag automatically

Adding `unless on() (max(pg_replication_lag{type="patroni"}) > 115)` to the rule
was considered and rejected, for three measured reasons: at 08-21 16:05 max lag
was 113.6s so the gate would not have fired anyway (that stamp was a write-path
stall); the gate blinds both offline rules at 7 of 8,603 5-minute steps over
30 days with no signal that suppression happened, which is the fail-silent class
this rule spent two review rounds removing; and `pg_replication_lag` is itself
absent at 38 of those steps, so the mechanism is least available exactly during
severe database trouble. The check therefore lives here, in step 1, where you
can see it applied.

## Escalation

Escalate to the Global Search team if nodes cannot be brought back or if fleet
capacity is at risk. As an immediate mitigation for user-facing slowness,
Zoekt **searching** can be disabled while leaving indexing on, from
`Admin > Settings > Search > Exact code search > Enable searching` — see
[Enabling/Disabling Zoekt search](../README.md#enablingdisabling-zoekt-search).

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)

## Related links

- [Exact code search service](../README.md)
- [ZoektNodeOfflineWarning](./ZoektNodeOfflineWarning.md)
- [Node offline and lost detection](../README.md#node-offline-and-lost-detection)
