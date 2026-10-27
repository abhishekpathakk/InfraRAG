# ElasticsearchExporterClusterUnreachable

## Overview

The `prometheus-elasticsearch-exporter` named in `{{ $labels.job }}` is running
and being scraped, but it cannot reach the Elasticsearch cluster it is pointed
at. `elasticsearch_clusterinfo_up` reads `0`.

The consequence is larger than one missing dashboard. When this reads `0`, every
node-level and index-level `elasticsearch_*` family for that `type` is **absent,
not zero** — the exporter drops from ~214 published metric families to about 7
scrape-health and cluster-info series. Saturation alerts are written as
`gitlab_component_saturation:ratio{...} > on(component) group_left slo:...`, and
a `>` against an absent left-hand side yields no series rather than a breach. So
the affected cluster's disk, CPU, JVM heap and thread-pool alerts stop being able
to fire at all, including `component_saturation_slo_out_of_bounds:elastic_disk_space`,
which is `s2`. The cluster can fill its disks without paging anyone.

The two SLIs declared in `metrics-catalog/services/search.jsonnet`
(`elasticsearch_searching`, `elasticsearch_indexing`) read counters only this
exporter supplies, so they go quiet too.

## Services

- [Search](../../search/README.md)
- [Elastic Cloud](../elastic-cloud.md)
- [Advanced Search cluster metrics](../advanced-search-cluster-metrics.md)

## Metrics

Confirm the alert and identify which exporter, with the healthy one as a control:

```promql
elasticsearch_clusterinfo_up
```

Both the `search` and `logging` exporters publish `elasticsearch_*` into the same
datasource and are told apart **only** by the `type` label. If one reads `1` and
the other `0`, the datasource and the query are fine and the problem is that one
exporter.

The second tell, which needs no prior knowledge of what should exist:

```promql
count by (type) (count by (__name__, type) ({__name__=~"elasticsearch_.*", environment="gprd"}))
```

A count in single digits against a sibling in the hundreds is a failed
connection, not a collector that was turned off.

Whether the saturation inputs are gone:

```promql
count by (component) (gitlab_component_saturation:ratio{env="gprd", type="search"})
```

While healthy this returns `elastic_cpu`, `elastic_disk_space`,
`elastic_jvm_heap_memory`, `elastic_single_node_cpu`,
`elastic_single_node_disk_space`, `elastic_thread_pools` and `open_fds`. Only
`open_fds` surviving means the six `elastic_*` alerts are inert.

## Alert Behavior

`for: 1h` is deliberate. The exporter pod restarts routinely — gprd saw 55
restarts in 90 days — and each restart takes the signal to `0` for minutes. An
hour is long enough that no restart reaches it and short enough that a real
outage is caught the same shift.

The alert is blind to the exporter pod being absent entirely, because that leaves
no series to evaluate. That case is covered by the Kubernetes pod alerts; adding
an `absent()` clause here would double-page on every restart.

Silence only when a cluster is being retired deliberately, and only after
confirming the exporter is not still the sole source for a live cluster's
saturation alerts.

## Severities

`s3`. Nothing is user-visible at the moment this fires — search keeps serving,
and indexing keeps running. What is lost is the ability to see the cluster
saturate, which is why it should not be left open: the failure it hides is `s2`.

Escalate to `s2` if the cluster it monitors is known to be under disk or heap
pressure, since that is exactly the state nothing else can now observe.

## Recent changes

**A cluster upgrade is the most likely cause, and it will not appear in the
exporter's own repository.** GitLab upgrades this cluster blue/green: a new
Elastic Cloud deployment is created, traffic is cut over, and the old deployment
is deleted in a separate follow-up change a week later. The exporter's URI lives
in `gitlab-com/gl-infra/argocd/apps` under
`services/es-exporter-search/env/<env>/clusters/<cluster>/values.yaml` and is not
part of either change, so deleting the old deployment silently strands it.

Check the production tracker for a recent
`Global search Elasticsearch cluster upgrade cleanup` change before looking
anywhere else.

## Troubleshooting

Read the exporter's own error text. It is in the pod logs, not in metrics:

```plaintext
kubectl -n elasticsearch-exporter logs -l app=prometheus-elasticsearch-exporter --tail=50
```

Those logs also ship to `pubsub-monitoring-inf-gprd`, filtered on
`kubernetes.pod_name`, which is the route when cluster access is not to hand.

The error text distinguishes the two causes that look identical from metrics:

| Log line | Cause |
| --- | --- |
| `HTTP Request failed with code 404` | The endpoint no longer exists. The deployment was deleted or replaced — the URI is wrong. |
| `HTTP Request failed with code 401` | Credentials. The external secrets pin `version: "1"` with `refreshInterval: 0`, so a password rotated on the Elastic side is never re-fetched. |
| connection refused, timeout, TLS error | Network path or certificate. |

Confirm a 404 from outside the cluster — the endpoint answering
`{"ok":false,"message":"Unknown resource."}` on `GET /` means the hostname
resolves to the shared Elastic Cloud proxy but names no deployment:

```shell
curl -sS "https://<host>:9243/"
```

A live deployment answers `401` with a `WWW-Authenticate` header instead, which
is a useful positive control that the probe itself works.

## Possible Resolutions

- **Endpoint gone (404).** Find the current deployment in the
  [Elastic Cloud console](https://cloud.elastic.co/deployments) and update the
  `es.uri` in `services/es-exporter-search/env/<env>/clusters/<cluster>/values.yaml`
  in `gitlab-com/gl-infra/argocd/apps`. Check the sibling environment at the same
  time: staging and production are upgraded a few days apart, so both are usually
  stranded by the same pair of changes.
- **Credentials (401).** Rotate the Vault entry and bump the pinned `version:` in
  `values-vault-secrets.yaml`; leaving the version pinned means the new secret is
  never fetched.
- Restarting the pod does not help in either case. Every restart comes up unable
  to reach the cluster, which is why the restart count is not a useful signal
  here.

After the fix, confirm recovery on all three: `elasticsearch_clusterinfo_up`
reading `1`, the family count back in the hundreds, and the six `elastic_*`
components present in the saturation query above. The first alone is not enough —
it is one of the handful of series that survives the outage.

## Dependencies

- [Elastic Cloud](https://status.elastic.co/)
- [Mimir](../../mimir/README.md)

## Escalation

- `#g_global_search_alerts` for the Search team, who own the `search` exporter;
  the alert carries `team: global_search`, so it routes there automatically.
- `#g_infra_observability_alerts` for the Observability team, who own the
  `logging` exporter (`services/service-catalog.yml`); the alert carries
  `team: observability`, so it routes there automatically.
- `#production` if the cluster itself is suspected to be saturating.
- The `search` exporter (`es-exporter-search`) stays with Search, not
  Observability, despite both exporters sharing this alert:
  [observability/team#4615](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/work_items/4615)
  trimmed the logging and monitoring exporters from Observability's scope and
  explicitly excluded `es-exporter-search`.

## Definitions

- [Link to the definition of this alert for review and tuning](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules-jsonnet/elasticsearch-exporter-alerts.jsonnet)
- [Link to edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/elastic/alerts/ElasticsearchExporterClusterUnreachable.md)

## Related Links

- [Related alerts](./)
- [Advanced Search cluster metrics](../advanced-search-cluster-metrics.md)
