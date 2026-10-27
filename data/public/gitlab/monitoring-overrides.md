# Monitoring Overrides

A service definition's `monitoring` stanza tunes how SLO alerts are generated for
that service. It is also the configuration surface behind the `monitoring.*` options
in [the reference architecture](../../reference-architectures/README.md#options), so
a change here affects consumers outside this repository as well as GitLab.com.

The schema is defined and validated in
[`libsonnet/servicemetrics/service_definition.libsonnet`](../../libsonnet/servicemetrics/service_definition.libsonnet),
and read back out in
[`libsonnet/slo-alerts/service-alerts-generator.libsonnet`](../../libsonnet/slo-alerts/service-alerts-generator.libsonnet).

## Dimensions

SLO alerts are generated per aggregation set, and each aggregation set reads its
configuration from a different key under `monitoring`:

| Aggregation set   | `monitoring` key | Alert suffix  | Generated when                    |
| ----------------- | ---------------- | ------------- | --------------------------------- |
| `component`       | `component`      | none          | the SLI is not shard-monitored    |
| `component_shard` | `shard`          | `SingleShard` | the SLI is shard-monitored        |
| `component_node`  | `node`           | `SingleNode`  | `monitoring.node.enabled` is true |

`regional_component` has no mapping under `monitoring`, so it ignores everything
below; it is gated by the service's `regional` flag instead.

Shard and node behave differently here, which is easy to get wrong:

* Shard alerts replace the component alert. An SLI is either alerted on as a whole
  or per shard, never both.
* Node alerts sit alongside the component alert, so a node-monitored SLI produces
  both.

An SLI is shard-monitored when its `shardLevelMonitoring` flag is set. Setting
`monitoring.shard.enabled: true` turns that flag on for every SLI in the service;
an individual SLI opts back out with `shardLevelMonitoring: false`.

```jsonnet
monitoring: {
  component: {
    overrides: {},
  },
  shard: {
    enabled: false,
    overrides: {},
  },
  node: {
    enabled: false,
    thresholds: {},
    overrides: {},
  },
}
```

`thresholds` on the `node` dimension sets the SLO thresholds (`apdexScore`,
`errorRatio`) used by node-level alerts, replacing the SLI's own
`monitoringThresholds` for that dimension.

## Per-SLI overrides

`overrides` is a map keyed by SLI name. Every key is optional; leaving an SLI out
of the map, or leaving a field out of its entry, keeps the default.

| Field                         | Type                       | Dimensions   | Effect                                            |
| ----------------------------- | -------------------------- | ------------ | ------------------------------------------------- |
| `alertForDuration`            | promql duration            | all          | Overrides the alert's `for:` duration.            |
| `minimumSamplesForMonitoring` | number                     | all          | Overrides the minimum sample size for alerting.   |
| `trafficCessation`            | object, see below          | all          | Tunes the per-dimension `TrafficCessation` alert. |
| `thresholds`                  | map of shard to thresholds | `shard` only | Sets a distinct SLO threshold per shard value.    |

`minimumSamplesForMonitoring` is the sample size below which the SLI is excluded from
alerting entirely; see [Minimum Thresholds](service-level-monitoring.md#minimum-thresholds)
for why we count samples rather than an ops rate.

`trafficCessation` takes three optional fields:

| Field      | Type            | Default | Effect                                             |
| ---------- | --------------- | ------- | -------------------------------------------------- |
| `burnRate` | promql duration | `30m`   | The ops rate window the `== 0` check rides on.     |
| `for`      | promql duration | `5m`    | How long the rate must stay at zero before firing. |
| `selector` | object          | none    | Restricts which series the cessation alert covers. |

`burnRate` must be a burn rate the aggregation set actually records, otherwise
generation fails. Narrowing `burnRate` also raises the effective minimum ops rate,
because the minimum sample count is held over a shorter window. See
[Configurable traffic cessation thresholds](configurable-traffic-cessation-thresholds.md)
for the reasoning, and [Traffic Cessation Alerts](traffic-cessation-alerts.md) for
what these alerts do.

These overrides deliberately do not reach the `TrafficAbsent` alert, which has a
different noise profile.

### Per-shard thresholds

`thresholds` exists only on the `shard` dimension, and it does something the other
fields cannot: it sets a different threshold per shard value. Each overridden shard
gets its own alert, and the shards left out get a single catch-all alert at the SLI's
default threshold. There is no equivalent for `node` or `region`; adding one would
mean teaching both the alert generator and the recording rule generator about the
dimension label.

The SLI must have `shardLevelMonitoring: true` for it to appear in
`monitoring.shard.overrides` at all.

## Example

From [`metrics-catalog/services/sidekiq.jsonnet`](../../metrics-catalog/services/sidekiq.jsonnet):

```jsonnet
monitoring: {
  shard: {
    enabled: true,
    overrides: {
      sidekiq_execution: {
        thresholds: {
          'urgent-other': { apdexScore: 0.985 },
          'urgent-cpu-bound': { apdexScore: 0.99 },
        },
      },
    },
  },
}
```

Here `urgent-other` and `urgent-cpu-bound` each get their own apdex SLO, and every
other shard is alerted on together at the SLI default.

## Validation

Override entries are validated when the service definition is evaluated, before
any rules are generated. Unknown keys and wrong types are rejected rather than
silently ignored, so a typo fails loudly:

```console
field monitoring.shard.overrides: sidekiq_execution: unknown key(s) ["catchall"]
(allowed: ["alertForDuration", "minimumSamplesForMonitoring", "thresholds", "trafficCessation"])
```

A `burnRate` that the aggregation set does not record is caught slightly later, at
generation time.

## Changelog

### v4.293.0 — per-shard thresholds moved under `thresholds`

Before v4.293.0, `monitoring.shard.overrides` mapped an SLI straight onto its shards:

```jsonnet
// Before v4.293.0 — no longer valid
overrides: {
  sidekiq_execution: {
    'urgent-cpu-bound': { apdexScore: 0.99 },
  },
}
```

Those per-shard thresholds now live under a `thresholds` key, which frees the SLI
level up for `alertForDuration`, `minimumSamplesForMonitoring` and
`trafficCessation`, and makes shard entries the same shape as component and node
entries:

```jsonnet
// v4.293.0 and later
overrides: {
  sidekiq_execution: {
    thresholds: {
      'urgent-cpu-bound': { apdexScore: 0.99 },
    },
  },
}
```

The generated rules are unchanged; only the input shape moved. The same release
began rejecting unknown keys, so the old shape fails validation instead of being
ignored. If you are pinned below v4.293.0, nest your existing shard maps under
`thresholds` as you upgrade.
[tenant-observability-config!228](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/tenant-observability-config/-/merge_requests/228)
is a worked example.

This shipped as a minor version bump rather than a major one, which broke consumers
without warning. See [gitlab-org/gitlab#618044](https://gitlab.com/gitlab-org/gitlab/-/issues/618044).
