# ZoektSearchErrorRateHigh

## Overview

Exact code searches **made through the Search API** are burning the zoekt
service's error budget fast enough to matter. This is a **multiwindow burn-rate
alert**, not a fixed error-ratio threshold: it fires when the error ratio
exceeds 14.4x the budget on both the 1h and 5m windows at once, or 6x the
budget on both the 6h and 30m windows, while the scored population is carrying
at least 1 request/s.

The budget is `1 - errorRatio` from the zoekt service's declared
`monitoringThresholds` in
[`metrics-catalog/services/zoekt.jsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/zoekt.jsonnet)
(`errorRatio: 0.9999`) — one error in every ten thousand searches. The alert
multiplies that budget rather than replacing it, so the SLO stays defined in
exactly one place. 14.4x over 1h exhausts 2% of a 30-day budget; 6x over 6h
exhausts 5%. This is the same shape the metrics-catalog framework generates for
every service SLI (compare `ZoektServiceZoektSearchingErrorSLOViolation`).

The counters come from `Gitlab::Metrics::GlobalSearchSlis.record_error_rate`
([`lib/gitlab/metrics/global_search_slis.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/metrics/global_search_slis.rb)),
filtered to `search_type="zoekt"`, to the three Search API `endpoint_id`s, and
to `search_scope="blobs"` at project or group level.

## Scored population: project and group blob search on the API, and why

**This alert does not cover exact code search from the web UI, and it does not
cover every Search API request either.** The two exclusions no longer have the
same cause: the web path is excluded by this alert's endpoint scoping, while
the remaining API-side exclusion is an instrumentation limitation.

`gitlab_sli_global_search_{total,error_total}` is a Labkit `ErrorRate` SLI, and
per `Labkit::ApplicationSli#increment` the **denominator only advances when
`record_error_rate` is called at all**.

### The web path DOES record, under a different endpoint id

Exact code search from the web UI is not served by `haml_search_results`:
`SearchController#show` runs it `unless multi_match?(...)`, and
[`ee/app/controllers/ee/search_controller.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/app/controllers/ee/search_controller.rb)
overrides `multi_match?` to `scope == 'blobs' && search_type == 'zoekt'`. The
results come from the GraphQL `blobSearch` query instead, and that resolver now
records the error SLI on **every** exit path, success included, from an
`ensure` block:
[`blob_search_resolver.rb#L118-128`](https://gitlab.com/gitlab-org/gitlab/-/blob/c74c791b205ad3578d3a8b4eca00b133b4788677/ee/app/graphql/resolvers/search/blob/blob_search_resolver.rb#L118-128).
`error:` is true only for `@search_results.nil? || @search_results.server_error?`,
so a rejected query counts in the denominator as a non-error.

That landed in `8d329960ff07` (2026-09-10) and is live on GitLab.com: it is an
ancestor of revision `7b3e9ba6c77`, which `GET /api/v4/version` reported on
2026-09-14. So the web population's denominator now counts successes, and the
`+Inf`-prone shape this section used to describe is gone.

**It is still outside this alert**, for a different reason: `endpoint_id` is
taken from the request's `ApplicationContext` `caller_id`
(`GlobalSearchSlis#endpoint_id`), so a web search records under the GraphQL
controller's id, and the alert enumerates only the three Search API endpoint
ids (see below). Rescoping to include the web population is a live option, but
wants a fresh production measurement of that population's ratio first — none
has been taken since the change landed.

### A never-successful population survives inside the API endpoints

Scoping to the API endpoints is necessary but **not sufficient**. The API path
([`lib/api/search.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/api/search.rb))
calls `record_error_rate` from an `ensure` block on every request, but it calls
`record_apdex` only on the success path, and the `ensure` scores a request that
never reached the benchmark as an error. Sub-populations that always
short-circuit therefore increment `total` and `error_total` and never
`apdex_total` — a constant-100% ratio with nothing for an alert to detect.

Measured on production gprd over 7 days, `search_type="zoekt"` on the three
Search API endpoint ids:

| Population | total | error | apdex_total | Scoreable? |
| --- | ---: | ---: | ---: | --- |
| `search_level="global"`, blobs | 265.4 | 265.4 | **0** | no |
| project `wiki_blobs` | 301.1 | 301.1 | **0** | no |
| project `milestones` | 4.0 | 4.0 | **0** | no |
| project `issues` | 2.0 | 2.0 | **0** | no |
| project blobs | 4,657,721 | 210.3 | 4,574,558 | yes (0.98) |
| group blobs | 1,737,178 | 14.0 | 1,728,162 | yes (0.99) |

The four degenerate rows are 100% error by construction and contributed **71.9%
of the alert's 7-day numerator**. With them included, a plain
`ratio_1h > 0.0001` alert would have paged **~40 times in that week** while the
scoreable population ran at **0.35x** the declared budget — i.e. production was
never burning its zoekt error budget. That is why the scored population is
`search_scope="blobs"` at project or group level, and why the alert is a
burn-rate rather than a retuned threshold.

Three consequences for the on-caller:

- **A quiet alert says nothing about web search error rates — but the web
  population is now directly measurable.** Since the resolver's `ensure` block
  landed, the web path's own error ratio can be read straight off the same SLI
  the alert uses, restricted to the GraphQL endpoint id rather than the API
  ones:

  ```promql
  sum(rate(gitlab_sli_global_search_error_total{env="gprd", search_type="zoekt", search_scope="blobs", endpoint_id=~"GraphqlController#execute.*"}[1h]))
  /
  sum(rate(gitlab_sli_global_search_total{env="gprd", search_type="zoekt", search_scope="blobs", endpoint_id=~"GraphqlController#execute.*"}[1h]))
  ```

  Run it before reaching for a proxy — it is the user-visible ratio, not a
  stand-in. Two caveats: this runbook has taken **no** production reading of it
  since the change landed, so there is no baseline here to compare against; and
  `zoekt` has **no** `rails_request` SLI of its own — it declares only
  `zoekt_searching` and `zoekt_tasks`.

  The `rails_request` SLIs remain the cross-check for "did Rails 5xx", on
  whichever service carries the endpoint. **Which service that is was measured,
  not assumed** (gprd, 7d, instant queries through the `mimir-gitlab-gprd`
  datasource proxy):

  | Query | Series | Result |
  | --- | ---: | --- |
  | `sum by (type, endpoint_id) (increase(gitlab_sli_rails_request_total{env="gprd", type="web", endpoint_id=~"GraphqlController#execute.*"}[7d]))` | **0** | no series — GraphQL is **not** on `web` |
  | `sum by (type) (increase(gitlab_sli_rails_request_total{env="gprd", endpoint_id="GraphqlController#execute"}[7d]))` | 2 | `type="api"` 443,093,623; `type="ai-assisted"` 1,200,739 |
  | `sum by (type, endpoint_id) (increase(gitlab_sli_rails_request_total{env="gprd", endpoint_id=~"GraphqlController#execute:getBlobSearch.*"}[7d]))` | 2 | `api` / `…:getBlobSearchCountQuery` 165,300; `api` / `…:getBlobSearchQuery` 143,298 |
  | `sum by (type, endpoint_id) (increase(gitlab_sli_rails_request_total{env="gprd", type="web", endpoint_id=~"SearchController#.*"}[7d]))` | 6 | `#autocomplete` 2,783,642; `#opensearch` 2,182,263; `#count` 2,134,532; `#show` 1,006,973; `#aggregations` 1,946; `#settings` 0 |
  | `sum by (type) (increase(gitlab_sli_rails_request_total{env="gprd", type="zoekt"}[7d]))` | **0** | confirms `zoekt` has no `rails_request` SLI |

  So there are **two** places to look, not one:

  - the **`web`** service's `rails_request` SLI for the `SearchController`
    family (`#show`, `#count`, `#autocomplete`) — that is what a browser search
    request hits;
  - the **`api`** service's `rails_request` SLI for the GraphQL half, at the
    named operations `GraphqlController#execute:getBlobSearchQuery` and
    `GraphqlController#execute:getBlobSearchCountQuery`. Those operation-level
    endpoint ids are individually addressable, so this is **not** the coarse
    "all GraphQL traffic" proxy an earlier version of this runbook described.

  Caveat from the same measurement: `rails_request_error_total` over 7d is
  **0** for both blobSearch operations and for `SearchController#show`,
  `#count` and `#autocomplete`. These SLIs are the right place to look, but
  they were flat over the measured week — a non-zero reading is signal, and a
  zero reading does not prove the user-visible search path was healthy, only
  that Rails returned no 5xx there.
- **A quiet alert also says nothing about short-circuited API requests**
  (global-level blobs, wiki_blobs, issues, milestones). Those are 100% "error"
  in the SLI at all times, so there is nothing for an alert to detect.
- **`ZoektSearchApdexBurn` is NOT scoped this way and does not need to be** —
  `record_apdex` *is* called on the GraphQL success path, so its denominator is
  complete for both populations.

One `gitlab-org/gitlab` fix has landed and one has not:

- **Done.** The zoekt web path records the `global_search` error SLI on success
  (`8d329960ff07`), so the web population's ratio is meaningful — it is simply
  outside this alert's endpoint scoping.
- **Still open.** The API path counts requests that short-circuit before the
  search runs as search errors. Re-read at
  [`lib/api/search.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/api/search.rb):
  the `ensure` block records `error: @search_duration_s.nil? || status >= 500`,
  and a request rejected by `bad_request!`/`forbidden!` never reaches the
  benchmark, so `@search_duration_s` is nil and the request scores as an error
  regardless of its status code. The four degenerate rows above are therefore
  still 100% error by construction.

So this alert's scoping is a containment for the second gap, not a fix for it.
Whether the declared `errorRatio: 0.9999` is the right budget for this
population is a separate, open product question; Global Search SLI calibration
is covered by
[gitlab-org/gitlab#627960](https://gitlab.com/gitlab-org/gitlab/-/issues/627960).

## Firing margin: this alert has never evaluated true, and that is the correct answer

Stated explicitly because "0 pages/week" alone reads as either triumph or
silencing depending on the reader. Measured on production gprd over 7 days at a
300s step, on the scored population:

| Window | Median ratio | p95 | **Worst observed** | Gate | Headroom at the worst point |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ratio_1h` | 2.61e-05 | 1.22e-04 | **3.22e-04** | 1.44e-03 (14.4x) | **4.5x below** |
| `ratio_6h` | 3.15e-05 | 7.87e-05 | **1.20e-04** | 6.0e-04 (6x) | **5.0x below** |

Zero of 2,017 evaluated steps crossed either gate. So the first real page will
be the first time this rule has ever evaluated true.

The counterfactual is what distinguishes a wide margin from a silenced alert.
Holding the real denominators and scaling the numerator by *k*:

| k | Firing steps of 2,017 | Pages/week (honouring `for: 2m`) |
| ---: | ---: | ---: |
| 1 | 0 | **0** |
| 2 | 0 | 0 |
| 5 | 1 | 0 |
| **10** | **86** | **15** |
| 20 | 561 | 65 |
| 50 | 777 | 87 |
| 100 | 796 | 88 |

A 10x deterioration of the real error rate pages 15 times a week; a 5x one is
correctly below the gate. The alert is live, not muted — production simply runs
about 4.5x inside its tightest gate.

The volume gates are never the binding constraint on this population: the 1h
request rate has a 7d minimum of 5.63/s against a 1/s gate, and the 6h rate a
minimum of 6.85/s against 0.16667/s.

## How this differs from the ZoektService* SLO alerts

Same distinction as for [ZoektSearchApdexBurn](./ZoektSearchApdexBurn.md):

| Alert | Measures |
| --- | --- |
| **This alert** | Rails-side `global_search` error SLI — searches that failed from the *user's* point of view, including a Zoekt call that timed out or a gateway error |
| `ZoektServiceZoektSearchingErrorSLOViolation` | `zoekt_search_failed_total` — searches the Zoekt binary itself considered failed |

An error that never reached Zoekt (gateway down, connection refused, Rails
exception before the call) shows up **only here**. That makes this the better
alert for "is code search working", and the service SLO alert the better one for
"is Zoekt working".

## Alert behavior

Fires when **both** windows of a burn-rate pair exceed the gate at the same
time, and the scored population is carrying enough traffic for the ratio to
mean something:

| Pair | Windows | Gate | Volume gate |
| --- | --- | --- | --- |
| Fast | 1h **and** 5m | `> 14.4 x 0.0001` = 0.00144 | 1h rate `>= 1/s` |
| Slow | 6h **and** 30m | `> 6 x 0.0001` = 0.0006 | 6h rate `>= 0.16667/s` |

`for: 2m`, because the two-window agreement is itself the sustain requirement —
a long `for:` on top of it only delays the page.

The page text names **both** multipliers rather than one. An earlier version
interpolated only the fast rate and read "at least 14.4x the budget" whichever
arm had fired; measured with promtool, a steady 0.061% ratio fires through the
6h+30m pair and that sentence overstated the burn by 2.4x. The slow arm is also
the likelier path — its gate is 2.4x lower and a sustained regression crosses
the 6h/30m windows first — so read `$value` and the pair gates together rather
than assuming the fast arm fired.

The volume gate replaces the older trailing `sum(rate(...total)) > 0` guard and
is strictly stronger. That guard was load-bearing: the claim that "a zero
denominator yields NaN, which does not satisfy `>`" holds only while the
numerator is *also* zero, and a non-zero numerator over a zero-rate denominator
evaluates to `+Inf`, which satisfies every comparison and pages with `+Inf%` in
the annotation. `>= 1/s` excludes that case and the handful-of-errors-in-a-trough
case too. Measured over 7 days, the scored population's 1h request rate has a
minimum of 5.63/s and a median of 10.1/s, so 1/s sits far below any normal
trough. Both cases are asserted in the unit tests, and deleting the gate turns
the suite red.

Genuine traffic loss is **not** this alert's job — that is
`ZoektServiceZoektSearchingTrafficCessation` / `...TrafficAbsent`.

Severity **s3**, `alert_type: symptom`, `user_impacting: yes`.

Like the apdex burn alert, this one has **no `environment` annotation** — the
underlying counters carry `env`, not `environment`.

## First response

1. **Get the actual error.** The ratio tells you nothing about cause. Kibana:
   - [Rails logs](https://log.gprd.gitlab.net/goto/15b83f5a97e93af2496072d4aa53105f) —
     search-side exceptions land in `production_json.log`
   - [Zoekt health dashboard](https://log.gprd.gitlab.net/app/r/s/jR5H5)
   - `zoekt.log` for Zoekt-specific entries

2. **Split by scope and level** on the
   [observability dashboard](https://dashboards.gitlab.net/d/zoekt-observability/zoekt3a-zoekt-observability-orr).
   Errors confined to one `search_scope` point at a code path; errors across all
   scopes point at the transport or at the nodes.

3. **Check the gateway.** Zoekt sits behind an NGINX gateway
   (`zoekt.gprd.gke.gitlab.net`). A gateway or TLS problem produces errors that
   Zoekt itself never sees, which is exactly the case this alert catches and the
   service SLO alert misses.

4. **Check node availability.** Searches routed to a node that just went offline
   error until Rails notices (30 seconds — `ONLINE_DURATION_THRESHOLD`). A burst
   of errors coinciding with a node restart is this, and it self-resolves. See
   [ZoektNodeOfflineWarning](./ZoektNodeOfflineWarning.md).

5. **Check for OOM kills**, which produce exactly this signature — mid-search
   container death:
   [ZoektContainersRestartsDueToOOM](./ZoektContainersRestartsDueToOOM.md).

6. **Mitigation: disable Zoekt searching**, keeping indexing on, so searches
   fall back to Advanced Search:
   `Admin > Settings > Search > Exact code search > Enable searching`. See
   [enabling/disabling Zoekt search](../README.md#enablingdisabling-zoekt-search).

## Escalation

Escalate to the Global Search team. If searches are failing outright rather than
marginally over budget, use the search-disable mitigation first and diagnose
after — the fallback to Advanced Search keeps code search usable.

## Definitions

- [`libsonnet/alerts/zoekt-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/zoekt-alerts.libsonnet)
- Generated rules: [gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/search/autogenerated-gitlab-gprd-search-zoekt-alerts.yml),
  [gstg](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gstg/search/autogenerated-gitlab-gstg-search-zoekt-alerts.yml)
- Unit tests: [`test/mimir-rules/zoekt-alerts_test.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/test/mimir-rules/zoekt-alerts_test.yml)

## Known limitation

No `application_sli_aggregation:global_search:error:*` recording rule exists —
the `global_search` SLI is declared `kinds: [apdexKind]` only in
[`metrics-catalog/gitlab-slis/library.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/gitlab-slis/library.libsonnet),
so the framework generates apdex aggregations and no error aggregations, even
though Rails emits `gitlab_sli_global_search_error_total`. This alert therefore
reads the raw counters. Adding `errorRateKind` to that SLI definition would
generate the recording rules and let this alert use them; it is a follow-up on
the Zoekt observability epic and is worth doing, because raw-counter alerts are
more expensive to evaluate and cannot be reused by the error-budget tooling.

## Related links

- [Exact code search service](../README.md)
- [ZoektSearchApdexBurn](./ZoektSearchApdexBurn.md)
