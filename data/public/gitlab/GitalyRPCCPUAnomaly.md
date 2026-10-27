# GitalyRPCCPUAnomaly

## Overview

A Gitaly RPC is consuming an anomalous amount of CPU, sustained over multiple
hours. CPU here is attributed to the Git child processes each RPC spawns, via
the `gitaly_command_cpu_seconds_total` counter (which carries a `grpc_method`
label), aggregated across the whole fleet.

This is a **generic, per-RPC** detector: there is no hardcoded method list.
Every RPC that attributes CPU is compared against its *own* trailing one-week
baseline, and each fires as its own alert instance (identified by the
`grpc_method` label).

This alert is a corrective action from
[INC-13016](https://app.incident.io/gitlab/incidents/13016) /
[work item #29553](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29553).
In that incident a sustained spike in `ListBranchNamesContainingCommit` drove a
host into CPU saturation and degraded unrelated RPCs, and the only signal was
the aggregate apdex SLO, which fired roughly three hours after the ramp began.
This alert is designed to surface that kind of per-RPC anomaly early, before it
saturates a host. It applies to any expensive RPC, not just the one from that
incident.

## Services

- [Service Overview](../README.md)
- Team that owns the service: [Tenant Scale:Gitaly
  Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)

## Metrics

The alert compares a smoothed (1h) view of per-RPC CPU against a trailing
one-week baseline, and fires only when the value is both statistically
anomalous and above an absolute floor:

```promql
(
  (
    gitaly:cmd_cpu:rate5m:avg_over_time_1h{env="gprd"}
    - last_over_time(gitaly:cmd_cpu:rate5m:avg_over_time_1w{env="gprd"}[1h])
  )
  / clamp_min(last_over_time(gitaly:cmd_cpu:rate5m:stddev_over_time_1w{env="gprd"}[1h]), 3)
) > 3
and
gitaly:cmd_cpu:rate5m:avg_over_time_1h{env="gprd"} > 10
```

The raw per-RPC CPU rate can be inspected with:

```promql
sum by (grpc_method) (rate(gitaly_command_cpu_seconds_total{env="gprd"}[5m]))
```

- The query has **no `grpc_method` filter**. It evaluates every RPC. The
  z-score is inherently per-method (each RPC is compared against its own weekly
  baseline), so this stays per-RPC without a curated list.
- `> 3` is the z-score (sigma) threshold above the trailing one-week mean.
- The 1w baseline series are recorded on a 30m interval (to keep the weekly
  range queries cheap), so they are read with `last_over_time(...[1h])`. Without
  that wrapper, a 30m-cadence series would look absent to the ~1m alert
  evaluation for most of each cycle (the instant-vector lookback delta is ~5m),
  and `for: 30m` could never accumulate.
- The denominator is `clamp_min(stddev, 3)`, so a near-zero standard deviation
  cannot make the z-score blow up. This matters most during the cold-start
  period (see below), and it also means firing requires a real absolute
  deviation of at least `3 * 3 = 9` CPU-seconds/s above baseline, which normal
  daily cycling of a small method does not reach.
- The absolute floor (`> 10` CPU-seconds/s, fleet-wide) is what makes a blanket
  per-method rule safe: it suppresses rarely-called methods whose tiny standard
  deviation would otherwise make the z-score explode on any activity, and it
  ensures we only alert on RPCs consuming enough CPU to matter for host
  saturation, with no per-method tuning.
- The **1h averaging window is the "sustained" signal**: a short spike barely
  moves a one-hour mean, so `for:` is intentionally kept short (`30m`).
  Stacking a long `for:` on top of the 1h smoothing would mostly add detection
  latency without adding false-positive protection, eroding the lead time this
  alert exists to provide over the ~3h aggregate apdex SLO. Realistic
  time-to-fire on a sharp ramp is roughly 45 minutes to an hour.

## Alert Behavior

- Under normal conditions a method's smoothed CPU stays close to its weekly
  baseline and this alert is silent.
- The alert covers **all** CPU-attributing RPCs, each judged against its own
  baseline. If a specific method proves chronically noisy, silence just that one
  by adding a negative matcher (e.g. `grpc_method!~"SomeNoisyMethod"`) to the
  two `avg_over_time_1h` selectors in the alert, i.e. maintain a small denylist
  rather than an allowlist.
- Because CPU is aggregated across nodes (`sum by (grpc_method)`), a method
  saturating a *single* host may not move the fleet-wide sum enough to fire.
  Per-`fqdn` detection is a possible future enhancement (higher cardinality).
- The thresholds (sigma, floor, `for:` window) are tunables; expect to adjust
  them from production data.
- **Cold start:** for roughly the first week after these rules are deployed, the
  `avg_over_time_1w` / `stddev_over_time_1w` baselines have only as much history
  as has elapsed since rollout, so the baseline is still forming. The
  `clamp_min(stddev, 3)` denominator floor prevents the near-zero-stddev z-score
  blow-up that would otherwise cause false positives in that window, and the
  `> 9` CPU-seconds/s effective deviation requirement keeps a still-forming
  baseline from firing on normal variation. If extra caution is wanted for a
  given rollout, silence the alert (or temporarily raise the floor) for the
  first week while the baseline fills in.

## Severities

- Configured as **s4**: an early-warning cause alert with no direct user impact
  yet. It is meant to give responders lead time before saturation degrades the
  service-wide apdex SLO.

## Verification

- [Gitaly Load
  dashboard](https://dashboards.gitlab.net/d/gitaly-load/gitaly-load?orgId=1),
  see the "CPU time of Git commands per RPC" panel.
- Identify the offending method from the `grpc_method` label.
- Check host CPU saturation on the busiest Gitaly nodes and whether unrelated
  RPCs on those hosts are showing latency.
- Use Elasticsearch / logs to find whether a single repository or traffic
  source is driving the calls to that method.
- Watch for escalation to the adaptive concurrency limiter backing off
  ([GitalyAdaptiveLimiterBackoff](GitalyAdaptiveLimiterBackoff.md)) or dropped
  requests ([GitalyRequestsDropped](GitalyRequestsDropped.md)).

## Escalation

Gitaly has a Tier 2 rotation. Follow the [How to
Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)
guidance to page the team.

Several Slack channels are also available:

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)
- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)
- [#infrastructure_platforms](https://gitlab.enterprise.slack.com/archives/C02D1HQRTKQ)

## Definitions

- [Alert
  definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules-jsonnet/gitaly-rpc-cpu-anomaly.jsonnet)
  (Jsonnet source; the per-tenant YAML under `mimir-rules/` is generated from it)
- [Update the template used to format this
  playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
