# Advanced Search cluster metrics in Mimir

How to reach the gprd Advanced Search Elasticsearch cluster's own metrics when
investigating a `global_search` latency regression, and what to do when they are
not there.

## Two exporters, one metric namespace

Two `prometheus-elasticsearch-exporter` releases publish `elasticsearch_*` into
the `mimir-gitlab-gprd` datasource. They are told apart **only** by the `type`
label:

| `type` | Cluster | Scraped job |
| --- | --- | --- |
| `search` | Advanced Search (`gprd-indexing-20260608-33032c`) | `es-exporter-search-prometheus-elasticsearch-exporter` |
| `logging` | Logging | `es-exporter-logging-prometheus-elasticsearch-exporter` |

**Always pin `type="search"`.** An unqualified `elasticsearch_*` query today
returns logging-cluster data only, and reads as a healthy Advanced Search
cluster when it is nothing of the kind.

## First: is the search exporter actually up?

```promql
elasticsearch_clusterinfo_up{type="search"}
```

`1` means the cluster is being scraped and the queries below will work. `0` means
the exporter cannot reach or authenticate to the cluster, and **every**
node-level and index-level family is absent — not zero, absent. Use the logging
cluster as a control: if `elasticsearch_clusterinfo_up{type="logging"}` is `1`,
the datasource and your query are fine and the problem is the search exporter.

As of 2026-09-11 this reads `0`, and has since **2026-06-15T11:25Z**. Before that
timestamp every family below was present and queryable for the search cluster, so
a regression analysis over an older window can still use them.

A second tell, useful because it needs no prior knowledge of what should exist:

```promql
count by (type) (count by (__name__, type) ({__name__=~"elasticsearch_.*", environment="gprd"}))
```

Both exporters published 214 families while healthy. The search cluster's count
fell 214 → 9 at the outage minute and 9 → 7 when the exporter image moved to
v1.11.0 on 2026-07-07, leaving only the `cluster-info` and scrape-health meta
series — the shape a failed connection takes, not a collector that was turned
off. Compare against `type="logging"` rather than against a remembered number:
that cluster now publishes 150 after the series trimming in
[observability/team#4615](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/work_items/4615),
so the two counts are no longer expected to match.

When `up` is `0`, `elasticsearch_version{type="search"}` also reports
`version="0.0.0"` rather than a real version, so an Elasticsearch upgrade cannot
be ruled in or out from metrics.

## Periodic-operation queries

These answer "what runs on this cluster on a cycle, and did its schedule or scope
change". They need `elasticsearch_clusterinfo_up{type="search"} == 1`.

| Question | Query |
| --- | --- |
| Cluster-state work queueing | `max(elasticsearch_cluster_health_number_of_pending_tasks{type="search"})` |
| Cluster-state work waiting | `max(elasticsearch_cluster_health_task_max_waiting_in_queue_millis{type="search"})` |
| Merge/force-merge activity | `sum(rate(elasticsearch_indices_merges_total_time_seconds_total{type="search"}[10m]))` |
| Merge scope, in bytes | `sum(rate(elasticsearch_indices_merges_total_size_bytes_total{type="search"}[10m]))` |
| Flush cycles | `sum(rate(elasticsearch_indices_flush_time_seconds{type="search"}[10m]))` |
| Refresh cycles | `sum(rate(elasticsearch_indices_refresh_time_seconds_total{type="search"}[10m]))` |
| Thread-pool backlog, by pool | `sum by (exported_type) (elasticsearch_thread_pool_queue_count{type="search"})` |
| Rejections, by pool | `sum by (exported_type) (rate(elasticsearch_thread_pool_rejected_count{type="search"}[10m]))` |
| Per-node GC pressure | `sum by (name, gc) (rate(elasticsearch_jvm_gc_collection_seconds_count{type="search"}[10m]))` |

The node name is on `name` (`instance-00000000NN`), not `node` or `instance`.
The Elasticsearch thread pool is on **`exported_type`** — `type` is already taken
by the exporter-release label above, so Prometheus renamed the scraped one. The
`force_merge`, `flush`, `refresh`, `snapshot` and `warmer` pools are the periodic
ones; use `exported_type="force_merge"` to isolate force-merge specifically.

`elasticsearch_*` has no hot-threads equivalent. Use `elasticsearch_os_cpu_percent`
and `elasticsearch_breakers_tripped` as saturation proxies and go to the Elastic
Cloud console for thread-level detail.

ILM is **not** available for the search cluster even when the exporter is
healthy: `ilm: true` is set on the logging and monitoring releases only, so
`elasticsearch_ilm_status` and `elasticsearch_ilm_index_status` have never
carried a `type="search"` series. Snapshot and index-settings collectors are off
on both releases (`snapshots: false`, `indices_settings: false`). Reaching those
needs a config change, not a different query.

## Deciding whether a periodic operation changed

A rate that rose is not by itself a schedule change. Compare a window before the
suspected onset with a window after, on both the **mean** (scope) and the
**cycle** (schedule), and require a repeat before calling anything periodic:

1. Linearly detrend the window. A rising trend alone will otherwise produce a
   confident autocorrelation peak at an arbitrary lag.
2. Take the autocorrelation and keep only **interior local maxima**. A one-off
   step change decays monotonically, so its maximum always sits on the shortest
   lag; a real cycle puts a peak in the middle of the range.
3. Require the peak to **recur at twice the lag**. An operation that ran once
   does not.

Without step 3 a single step change plus normal noise scores as a 30-minute
cycle. Read the autocorrelation curve before believing any period: a smooth
monotone decay from the shortest lag is the signature of a level shift, not a
schedule.

## If the search exporter is down

The metrics are not recoverable by query — nothing was recorded. Route to the
cluster directly (Elastic Cloud console, Kibana Dev Tools; see
[README.md](README.md#administrative-accesslogin)) and raise the exporter
separately.

Deployment lives in `gitlab-com/gl-infra/argocd/apps` under
`services/es-exporter-search/`, with the cluster URI in
`env/gprd/clusters/gprd-gitlab-gke/values.yaml` and credentials sourced from
Vault by `values-vault-secrets.yaml`.

**Read the exporter's own error text before diagnosing anything.** It is in the
pod logs, not in metrics, and the two causes are indistinguishable from
Prometheus. Those logs also ship to `pubsub-monitoring-inf-gprd`, filtered on
`kubernetes.pod_name`, which is the route when cluster access is not to hand.

| Log line | Cause |
| --- | --- |
| `HTTP Request failed with code 404` | The endpoint no longer exists — the deployment was deleted or replaced, so the URI is wrong. |
| `HTTP Request failed with code 401` | Credentials. The external secrets are `refreshInterval: 0` with a pinned `version: "1"`, so a password rotated on the Elastic side is never re-fetched until someone bumps the version. |

The 2026-06-15 outage was the first, not the second. The cluster is upgraded
blue/green: a new Elastic Cloud deployment is created and cut over, then the old
one is deleted by a separate cleanup change about a week later. The exporter's
URI is in neither change, so the cleanup strands it. Both environments are
affected a few days apart — gstg broke 2026-06-12, gprd 2026-06-15, each within
minutes of its own cleanup change closing. Check the production tracker for a
recent `Global search Elasticsearch cluster upgrade cleanup` before anything
else.

Do **not** assume the collectors were never enabled. The search release turns off
only `indices_settings`, `indices_mappings`, `shards` and `snapshots`; index,
node, thread-pool, JVM and cluster-health stats are on by default and were being
collected normally until the connection broke. Check `clusterinfo_up` before
proposing a values change — a config fix will not restore metrics that a failed
connection is suppressing.

Two SLIs in `metrics-catalog/services/search.jsonnet` are declared against
metrics only this exporter supplies — `elasticsearch_searching` and
`elasticsearch_indexing`, both on `{type: 'search'}` counters. While the exporter
is down, those SLIs have no samples behind them even though their names still
resolve.

## What stops alerting while the exporter is down

The `component_saturation_slo_out_of_bounds:elastic_*` alerts on the `search`
service are silently inert, because a `>` comparison against an absent
left-hand side yields no series rather than a breach:

```promql
count by (component) (gitlab_component_saturation:ratio{env="gprd", type="search"})
```

That returns only `open_fds` today; before the outage it also returned
`elastic_cpu`, `elastic_disk_space`, `elastic_jvm_heap_memory`,
`elastic_single_node_cpu`, `elastic_single_node_disk_space` and
`elastic_thread_pools`. The same query with `type="logging"` still returns all of
them, so the saturation definitions are fine — their inputs are gone. Disk-space
saturation is `s2`; the cluster could fill up without paging anyone.
(`elastic_single_node_disk_space_cold` has an alert but no `type="search"` input
either side of the outage, so do not read its silence as a symptom.)

Nothing alerted on `elasticsearch_clusterinfo_up{type="search"}` for the first
91 days of the outage, which is why it went unnoticed.
[ElasticsearchExporterClusterUnreachable](alerts/ElasticsearchExporterClusterUnreachable.md)
now covers that. The autogenerated `*TrafficAbsent` alerts do not: their
`offset 1h unless` shape stops matching once the absence outlives the offset, so
they self-resolve while the cluster is still unreachable — measured on this
outage, 12 activations in the first six hours and none sixty days later.

The `count by (component)` query above remains the standing manual check: six
`elastic_*` components means the cluster is watched, none means it is not.
