# Configurable per-node traffic cessation thresholds

This is a design for letting a service tune how fast its per-node traffic
cessation alert fires, and which nodes it covers.

See [traffic-cessation-alerts.md](./traffic-cessation-alerts.md) for the
reference on what these alerts are and how to switch them on and off.

## Problem

The per-node `TrafficCessation` alert is slow. It checks the 30-minute ops
rate against zero:

    gitlab_component_node_ops:rate_30m{...} == 0
    and
    gitlab_component_node_ops:rate_30m{...} offset 1h >= 0.166

with `for: 5m`. Because the `== 0` check rides on `rate_30m`, the average has
to bleed off over half an hour before it reaches exactly zero. So even when a
node goes completely silent, the alert sits there waiting for the maths to
catch up, and detection lags the actual outage by a lot.

This came out of incident
[#22109](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22109),
where a single Gitaly node stopped serving traffic. The current rule fired
about 14 minutes after traffic stopped. A `rate_5m == 0` check with `for: 2m`
would have fired in about 2 minutes.

A shorter window is safe on the busy nodes but noisy on the quiet ones. Over
14 days on gprd, a 2-minute `rate_5m == 0` cessation would have fired zero
times on the SSD fleet (the minimum `rate_5m` anywhere never dropped below
0.62 rps), while every false positive came from the low-traffic `hdd` shard,
which drops to zero on its own during calm periods.

So a service needs to be able to ask for a faster window where its traffic
justifies it, and to leave its quiet nodes out of that faster check.

## How the alert is built today

`libsonnet/slo-alerts/traffic-cessation-alerts.libsonnet` generates the
cessation and absence rules. It picks two windows off the aggregation set:

- the **short period** (usually `5m`), used for the `TrafficCessation`
  `for:` and for the `TrafficAbsent` `== 0` comparison, and
- the **intermediate period** (usually `30m`), used for the
  `TrafficCessation` `== 0` check.

The alert descriptor carries a few related knobs already:
`trafficCessationSelector`, `minimumSamplesForTrafficCessation`, and
`alertForDuration`. The descriptors live in
`libsonnet/alerts/service-component-alerts.libsonnet`, and the per-node one
maps to the `component_node` aggregation set.

There's no way to change the window or the `for:` per service. They're
derived from the aggregation set's burn rates, so every service gets the
same 30m/5m behaviour.

## Proposed configuration

Add an optional `trafficCessation` block to the per-SLI node override map,
next to where `alertForDuration` already lives:

```jsonnet
monitoring: {
  node: {
    enabled: true,
    overrides: {
      goserver: {
        trafficCessation: {
          burnRate: '5m',                        // window for the `== 0` check
          'for': '2m',                           // alert `for:` duration
          selector: { shard: { ne: ['hdd'] } },  // merged into the alert selector
        },
      },
    },
  },
},
```

All three keys are optional:

- `burnRate` sets the window for the `== 0` check. It has to be one of the
  windows the aggregation set actually records. Defaults to the intermediate
  period (30m), so the rule is unchanged when omitted.

  Shortening this also tightens the minimum-traffic guard. The `offset 1h`
  check requires `minimumSamplesForTrafficCessation` ops (300 by default) in
  that same window an hour ago, so the effective floor is 0.166 rps over 30m
  but 1 rps over 5m. For a busy fleet that's irrelevant: Gitaly's SSD nodes
  sit at 100-350 rps and never dropped below 0.62 rps over a two-week sample,
  and the only nodes near the floor are the `hdd` shard we exclude anyway. For
  a lower-traffic service, check that a 1 rps floor won't mask a real
  cessation before picking a short window.
- `for` sets the alert `for:` duration. Defaults to the short period (5m).
- `selector` is merged into the alert's label selector, on top of the
  descriptor's `trafficCessationSelector`. Use it to exclude shards or scope
  the alert. Defaults to empty.

This only touches the `TrafficCessation` rule (signal present but zero). The
`TrafficAbsent` rule (signal missing) is left alone for now; its noise
profile is different and we haven't looked at it yet.

### Which aggregation sets support this

The override lookup keys off `aggregationSetToServiceMonitoringField` in
`service-alerts-generator.libsonnet`, which maps an aggregation set to a key
under `service.monitoring`. The mapped sets are `component` -> `component`,
`component_node` -> `node`, and `component_shard` -> `shard`, so `alertForDuration`
and `trafficCessation` overrides work for all three. `regional_component` is
not wired yet because nothing uses it.

The `monitoring.shard.overrides` map previously held per-shard SLO thresholds
directly (`overrides[<sli>][<shard>][<thresholdField>]`). To make room for the
common alert overrides at the SLI level, those thresholds now live under a
`thresholds` key (`overrides[<sli>].thresholds[<shard>][<thresholdField>]`),
matching the shape of the `component`/`node` override entries.

### Validation

Override entries are validated at config time. The per-SLI shape is expressed
with the `schema` and `mapOf` validator primitives, so unknown keys (e.g. a
`burnrate` typo) and wrong types are rejected before `make generate` rather
than silently falling back to defaults. An unrecorded `burnRate` is caught at
generation time, where the metric lookup uses `required=true`.

### Two config axes

This leaves us with two separate places that influence the traffic cessation
alerts, and they don't overlap cleanly:

- `sli.trafficCessationAlertConfig`, on the SLI itself, decides whether the
  cessation and absence alerts exist at all for a given aggregation set, and
  can attach a selector. It applies to both rules.
- `monitoring.node.overrides[<sli>].trafficCessation`, the new block, tunes
  the window, `for:`, and selector of the per-node cessation rule only.

Keeping them apart is deliberate for this change: `trafficCessationAlertConfig`
is a long-standing SLI attribute with a lot of callers, and folding it into
the `monitoring` stanza would be a wide refactor unrelated to the incident
fix. It's worth doing eventually so there's one obvious place to configure
these alerts, but that belongs in its own change. See [Later](#later).

## Where the code changes

1. `libsonnet/servicemetrics/service_definition.libsonnet` — document the
   `overrides[<sli>].trafficCessation` shape and extend the node validator in
   `validateMonitoring` to accept it.
2. `libsonnet/slo-alerts/service-alerts-generator.libsonnet` — read the
   override through the existing `getMonitoringConfig` path (the same one
   that already resolves `alertForDuration`) and pass it down to the traffic
   cessation generator. Because that lookup keys off the aggregation set, the
   config only applies to the `component_node` descriptor; everything else
   gets the default.
3. `libsonnet/slo-alerts/traffic-cessation-alerts.libsonnet` — accept the
   optional config and, for the `TrafficCessation` rule only, resolve the
   `== 0` metric with `aggregationSet.getOpsRateMetricForBurnRate(burnRate)`,
   use the configured `for:`, and merge in the selector. The
   `offset 1h >= requiredOpRate` guard keeps computing against the configured
   window so the minimum-op-rate maths stays correct.
4. `metrics-catalog/services/gitaly.jsonnet` — set the `goserver` SLI to the
   block above: 5m window, 2m `for`, excluding the `hdd` shard.

## Defaults and compatibility

Leaving `trafficCessation` out gives the same rules we generate today. Every
service except Gitaly should produce a zero diff after `make generate`, and
that diff is the easiest way to confirm we didn't change anything by accident.

## Testing

- Extend `libsonnet/slo-alerts/traffic-cessation-alerts_test.jsonnet` with
  fixtures that cover the default (unchanged) case and a configured case,
  asserting the expression uses `rate_5m`, `for: 2m`, and the `shard!="hdd"`
  selector.
- Run `make generate` and confirm the gprd Gitaly node cessation rule picks
  up the new window, `for:`, and selector, and that no other service's rules
  move.
- Run `make test` and
  `scripts/jsonnet_test.sh libsonnet/slo-alerts/traffic-cessation-alerts_test.jsonnet`.

## Later

The `hdd` shard and the `TrafficAbsent` alert are both worth revisiting. The
HDD nodes could get their own slower threshold instead of being dropped
entirely, and the absence alert has the same slow-window problem. Neither is
in scope here.

The two config axes described above are also a candidate for consolidation:
moving `sli.trafficCessationAlertConfig` under the `monitoring` stanza would
give a single home for all of this, but it touches every service that sets
it, so it needs its own change.
