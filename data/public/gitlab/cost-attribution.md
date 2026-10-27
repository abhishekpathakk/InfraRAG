# Cost Attribution

A service definition's `costAttribution` stanza declares how the service's cloud
cost is split across product feature categories. `make generate` turns it into a
recording rule in a new per-service rule file, in one of the Mimir tenants on the
[cost attribution allowlist](#which-tenant-the-rules-are-recorded-into), and the
cost warehouse reads that metric to apportion the service's bill.

The schema is defined and validated in
[`libsonnet/servicemetrics/service_definition.libsonnet`](../../libsonnet/servicemetrics/service_definition.libsonnet),
the rules are built in
[`libsonnet/recording-rules/cost-attribution-usage.libsonnet`](../../libsonnet/recording-rules/cost-attribution-usage.libsonnet)
and written out by
[`mimir-rules-jsonnet/cost-attribution-usage.jsonnet`](../../mimir-rules-jsonnet/cost-attribution-usage.jsonnet).
The reasoning behind the models lives in the
[cost attribution design document](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/21021);
this page only covers how to declare one.

## The metric

Every declaring service records the same metric:

```text
gitlab:feature_category:cost_attribution:usage:rate_5m{type="<service>", feature_category="<category>"}
```

`type` and `feature_category` are its only labels. The value is an intensity
sampled every five minutes: ops/s for a counter, bytes for a gauge, a constant for
the direct and weighted models. The warehouse integrates it over a day and turns
each category's share within the service into a share of the service's cost, so
the unit cancels and a counter, a gauge and a constant all work on the same metric.
The `rate_5m` suffix denotes the recording cadence, not the kind of value.

## Models

| `model`        | Meaning                                                             | Required                 | Optional          |
| -------------- | ------------------------------------------------------------------- | ------------------------ | ----------------- |
| `direct`       | The whole service belongs to one feature category                   | `featureCategory`        | `tenant`, `note`  |
| `proportional` | Split by a usage signal that carries a `feature_category` label     | `usage`                  | `tenant`, `note`  |
| `weighted`     | Split by fixed weights agreed with the service owner                | `weights`, `note`        | `tenant`          |
| `none`         | The recorded decision that this service has no model                | `note`                   |                   |

`tenant` becomes **required** when the service records into more than one
cost attribution tenant; see
[which tenant the rules are recorded into](#which-tenant-the-rules-are-recorded-into).

Any key not listed for a model is rejected, as is any other `model`. Leaving
`costAttribution` out altogether is different from `none`: absent means nobody has
decided yet and the warehouse reports the service as unattributed; `none` says the
same about the cost but records that it was looked at, which is why it needs a
`note`.

`featureCategory`, and every key of `weights`, must be a feature category from
[`stages.yml`](https://gitlab.com/gitlab-com/www-gitlab-com/-/blob/master/data/stages.yml).
`not_owned` is never allowed. `unknown` is allowed in `weights` only, for the
remainder that should fold into unattributed.

### Direct

```jsonnet
costAttribution: {
  model: 'direct',
  featureCategory: 'container_registry',
},
```

Produces one rule with `expr: vector(1)` and both labels.

### Proportional

```jsonnet
local rateMetric = metricsCatalog.rateMetric;

costAttribution: {
  model: 'proportional',
  usage: rateMetric(
    counter='gitlab_sql_duration_seconds_sum',
    selector={ db_config_name: { re: 'main(_replica)?' } },
  ),
  note: |||
    Client-side Rails query time as a proxy for storage and compute together.
  |||,
},
```

Produces one rule labelled with `type` only; `feature_category` comes from the
data. The expression is the usage metric aggregated by `feature_category` with
the tenant's own selector merged in: `env="gprd"` for `gitlab-gprd`,
`env="ops"` for `gitlab-ops`, and nothing at all for `runway`, which scopes
itself. Nothing else is added: in particular there is no `type="<service>"`
matcher, because the usage signal is often emitted by another service (Rails
emits `gitlab_sql_duration_seconds_sum`, not patroni). The owner's selector plus
the tenant's is the whole selector.

How the expression is rendered depends on the usage form, see
[the cost of the query](#the-cost-of-the-query) below. Either way the generated
file shows what Mimir evaluates.

### Weighted

```jsonnet
costAttribution: {
  model: 'weighted',
  weights: {
    source_code_management: 0.7,
    continuous_integration: 0.3,
  },
  note: |||
    2026-09: split agreed with the Gitaly team based on RPC volume by
    calling feature. Revisit when the CI storage tier moves off Gitaly.
  |||,
},
```

Produces one `vector(<weight>)` rule per key, sorted by feature category. Weights
are relative: they need not sum to one, the warehouse normalizes. Values must be
non-negative and at least one must be above zero; a zero weight is emitted as
declared. The `note` is required and should be dated and say where the numbers
came from, since nothing in the metric will.

### None

```jsonnet
costAttribution: {
  model: 'none',
  note: |||
    Internal monitoring infrastructure that serves engineering, not a product
    feature category. Its cost is deliberately reported as unattributed.
  |||,
},
```

Produces no rule. The `note` is required.

## Usage forms for `proportional`

`usage` accepts any metrics-catalog metric object that exposes
`aggregatedRateQuery`, which is the same interface an SLI's `requestRate` uses. The
generator calls it with `['feature_category']`, the tenant selector and `5m`, and
never builds PromQL itself.

|                 | Counter                             | Gauge                                     | Constant             |
| --------------- | ----------------------------------- | ----------------------------------------- | -------------------- |
| `usage`         | `rateMetric(counter)`               | `gaugeMetric(gauge)`                      | direct / weighted    |
| Recorded expr   | `sum by (fc) (rate(c[5m]))`         | `sum by (fc) (avg_over_time(g[5m]))`      | `vector(w)`          |
| Sample at *t*   | ops/s                               | bytes                                     | *w*                  |
| Warehouse, 1d   | ops/day                             | byte-seconds/day                          | *w* x 86400          |

A missing sample counts as zero usage for every form.

**`rateMetric`** (or `derivMetric`) for a counter:

```jsonnet
usage: rateMetric(
  counter='gitlab_sql_duration_seconds_sum',
  selector={ db_config_name: { re: 'main(_replica)?' } },
),
```

**`gaugeMetric`** for storage-shaped signals. Leave `samplingInterval` at its
default; it exists for precomputed Stackdriver rates. `gaugeMetric` has no
`wrapFunctions`, so a gauge that needs `label_replace` uses `customRateQuery`.

```jsonnet
usage: gaugeMetric(
  gauge='gitlab_storage_bytes_by_feature_category',
  selector={ storage_class: 'STANDARD' },
),
```

**`customRateQuery`** for anything neither constructor can express, including a
read of an existing recording rule. It ignores the selector and range interval it
is given, so `env="gprd"` is **not** merged in: the owner must scope the
environment in the query, and the validator cannot check that. The reviewer
should. This is how `patroni` declares its model, reading the rate that
[`rails.yml`](../../mimir-rules/gitlab-gprd/rails.yml) already records once a
minute, summed over pods:

```jsonnet
usage: customRateQuery(|||
  controller_action:gitlab_sql_duration_seconds_sum:rate5m{db_config_name=~"main(_replica)?",env="gprd"}
|||),
```

Or to shape a label the way the warehouse needs it:

```jsonnet
usage: customRateQuery(|||
  label_replace(
    avg_over_time(stackdriver_gcs_bucket_storage_googleapis_com_storage_total_bytes{env="gprd"}[5m]),
    "feature_category", "$1", "bucket", "gitlab-gprd-(.*)"
  )
|||),
```

**`costAttribution.fromSLIs`** to reuse the service's own SLIs. This is how `web`
declares its model: the request rate that drives the error budget also drives the
cost split, there is no metric name or selector to get wrong or to drift from the
SLI, and the rule reads the SLI's `sli_aggregations:` recording rule instead of
rescanning the raw metric.

```jsonnet
local costAttribution = import 'servicemetrics/cost-attribution.libsonnet';

usage: costAttribution.fromSLIs(['rails_request']),
```

Each named SLI must exist on the service, have a `requestRate` and list
`feature_category` in `significantLabels`. The SLI's `featureCategory` may stay
`not_owned`; only the label matters here. One SLI is used as is. Several are
stacked with `or` under a throwaway `_c` label and then summed, rather than added
with `+`, so a feature category that only one of the SLIs reports is still counted.

Check what the SLI counts before reusing it. An SLI measures what matters for the
SLO, which is not always what costs money: `patroni` reads
`controller_action:gitlab_sql_duration_seconds_sum:rate5m` instead of
`fromSLIs(['rails_primary_sql', 'rails_replica_sql'])` because those SLIs count
queries rather than query time and exclude Sidekiq, one of the largest database
consumers. The selector of the SLI also carries over unchanged: `web`'s expression
has `type="web"` because the SLI has it, not because the generator added it.

## The cost of the query

The rule runs every five minutes in the service's tenant. What it costs Mimir
depends on the usage form:

| Form                                                   | Rendered as                                         | Touches every 5m                          |
| ------------------------------------------------------ | --------------------------------------------------- | ----------------------------------------- |
| `fromSLIs`                                             | `sli_aggregations:<metric>:rate_5m{<SLI selector>}` | the recorded series, instant lookup       |
| `customRateQuery` over a recording rule                | the recorded series, as written                     | the recorded series, instant lookup       |
| `rateMetric`, `gaugeMetric`, raw `customRateQuery`     | the raw expression, `rate(...)` included            | every raw series over a 5m window         |

Reading a recorded series is cheap because the `rate()` and the fan-in over pods
and endpoints are already paid for, once a minute, by the recording rule; the
attribution rule reads the result and never rates the raw series again. Prefer
`fromSLIs` whenever the signal you want is an SLI of the service, and a
`customRateQuery` over an existing recording rule when it is not (`patroni`
reads `controller_action:gitlab_sql_duration_seconds_sum:rate5m` from
[`rails.yml`](../../mimir-rules/gitlab-gprd/rails.yml)). A hand-written rule can
be removed without anyone checking here, so name the dependency in the `note` or
a comment.

A `rateMetric` is deliberately **not** resolved through the recording rule
registry, even when some SLI records the same metric. The recorded series only
cover the union of the SLI selectors (the SQL SLIs exclude Sidekiq, for
instance), so resolving would silently narrow the model to whatever scope those
SLIs happen to have. `rateMetric` means this metric with this selector, and it
costs a raw scan of that metric's series every five minutes. Keep the selector
narrow; the cost is driven by the cardinality of the series matched, not by the
size of the result.

If the metric you want is not an SLI metric yet, the cheap path is to give it one:
a `requestRate`-only SLI with `userImpacting: false` and no apdex or error rate is
enough for the `sli_aggregations:` rule to exist (the `stackdriver` SLI in
[`logging.jsonnet`](../../metrics-catalog/services/logging.jsonnet) is the shape),
and then `fromSLIs` on it. The SLI's selector becomes the model's scope, so choose
it for the cost model, not only for the SLO.

## Which tenant the rules are recorded into

Cost attribution rules are generated into one of three Mimir tenants:

| Tenant | Share of attributed cloud cost | Largest services |
| ------------- | ------------------------------ | ----------------------------- |
| `gitlab-gprd` | ~69% | `gitaly`, `ci-runners`, `frontend` |
| `runway` | ~11% | `ai-gateway` (almost all of it) |
| `gitlab-ops` | ~1% | `pulp`, `teleport` |

This is an allowlist, held as `tenantAllowlist` in
[`cost-attribution.libsonnet`](../../libsonnet/servicemetrics/cost-attribution.libsonnet).
Every other tenant is either non-production (`gitlab-gstg`, `gitlab-pre`,
`packhorse-gstg`) or carries no attributed cloud cost, so a model declared on a
service that records only there would produce a series nothing is ever billed
against. Adding a tenant is also a change to the warehouse's ingestion contract,
not only to this repo, so it needs agreement on
[finops/team#499](https://gitlab.com/gitlab-com/gl-infra/finops/team/-/work_items/499)
first.

**Exactly one tenant per service, and the owner picks it.** A Mimir rule group
reads and writes the tenant it lives in, so the tenant decides both which
environment's usage drives the model and where the metric lands. The tenants
here are mostly environment partitions: ten services (`ci-runners`, `kube`,
`logging`, `monitoring`, `cloudflare`, `consul`, `cloud-sql`, `external-dns`,
`ci-orchestration`, `wiz-runtime-sensor`) list both `gitlab-gprd` and
`gitlab-ops` because they run a separate fleet in each environment, and each
tenant's copy of a rule sees only its own `env`. For such a service the stanza
must say which fleet the model is about:

```jsonnet
costAttribution: {
  model: 'proportional',
  tenant: 'gitlab-gprd',
  usage: ...,
  note: |||
    Production fleet only. The ops fleet serves internal CI and is not part
    of the billed ci-runners line.
  |||,
},
```

`tenant` must be on the allowlist and must be one of the service's own
`tenants`; anything else is rejected, since the generator only writes files for
the tenants a service records into and would otherwise emit nothing. When the
service records into exactly one allowed tenant there is no choice to make and
`tenant` may be omitted. Nothing is ever inferred when there is more than one.

A usage-producing model (`direct`, `proportional`, `weighted`) on a service that
resolves to no tenant **fails validation**. It used to validate and silently
record nothing, which is the worst of the available outcomes. `none` and an
absent `costAttribution` are exempt: they generate nothing anywhere, so any
service can record the decision that it has no model.

## What `make generate` produces

One file per declaring service, in that service's resolved tenant:

```text
mimir-rules/<tenant>/<type>/autogenerated-<tenant>-<type>-cost-attribution-usage.yml
```

```yaml
groups:
  - interval: 5m
    name: 'Cost attribution usage: patroni'
    rules:
      - expr: |
          sum by (feature_category) (
            controller_action:gitlab_sql_duration_seconds_sum:rate5m{db_config_name=~"main(_replica)?",env="gprd"}
          )
        labels:
          type: patroni
        record: gitlab:feature_category:cost_attribution:usage:rate_5m
```

The generated file belongs in the same MR as the declaration;
`make ensure-generated-content-up-to-date` fails otherwise. Services in
`service-catalog.yml` without a `metrics-catalog/services/*.jsonnet` definition
need a stub `serviceDefinition` before they can declare anything, including
`none`. Only `type` and `serviceLevelIndicators` are mandatory,
`serviceLevelIndicators: {}` validates, and
[`cloud-sql.jsonnet`](../../metrics-catalog/services/cloud-sql.jsonnet) is a
working template for a service with no Prometheus metrics of its own.

## Inspecting the series

In Grafana, with the datasource for the service's tenant
(`mimir-gitlab-gprd`, `mimir-runway` or `mimir-gitlab-ops`):

```promql
gitlab:feature_category:cost_attribution:usage:rate_5m{type="patroni"}
```

For a proportional model, the share each category receives over a day is what the
warehouse will compute:

```promql
sum_over_time(gitlab:feature_category:cost_attribution:usage:rate_5m{type="patroni"}[1d])
/ ignoring (feature_category) group_left
sum without (feature_category) (sum_over_time(gitlab:feature_category:cost_attribution:usage:rate_5m{type="patroni"}[1d]))
```

An empty `feature_category` value means the usage metric had samples without the
label; those fold into unattributed.
