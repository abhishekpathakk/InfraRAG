# Traffic Cessation Alerts

Because of the way alerts in Prometheus are built, it treats "no-signal" and "no-alert" conditions in the same way. A change may lead to an SLI no longer matching the metrics being emitted from the application, and when this happens, care needs to be taken to alert on this situation as Prometheus will not notify about this by default.

## Types of Traffic Cessation Alerts

Two types of traffic cessation conditions are monitored:

1. **Traffic Cessation**: traffic is non-absent, but zero for an
   extended period. Only if there were more than 300 operations an
   hour ago.
1. **Traffic Absence**: traffic is absent (missing, non-zero) for an
   extended period. Only if the metric was present an hour ago.

## Configuring Traffic Cessation Rules

Each SLI can be configured with different traffic cessation configurations.

### Defaults

The default is for the traffic cessation configuration to be omitted. When this is the case, all rules will default to on.

```jsonnet
    server: {
      userImpacting: false,
      requestRate: metricsCatalog.rateMetric(
        counter='gitaly_service_client_requests_total',
      ),
      significantLabels: [],
    },
```

### `trafficCessationAlertConfig: true`

This configuration is the same as the default, all rules are on.

```jsonnet
    server: {
      trafficCessationAlertConfig: true,
      userImpacting: false,
      requestRate: metricsCatalog.rateMetric(
        counter='gitaly_service_client_requests_total',
      ),
      significantLabels: [],
    },
```

### `trafficCessationAlertConfig: false`

This configuration disables all types of traffic cessation alerts for a service. Use this for occassional services.

```jsonnet
    server: {
      trafficCessationAlertConfig: false,
      userImpacting: false,
      requestRate: metricsCatalog.rateMetric(
        counter='gitaly_service_client_requests_total',
      ),
      significantLabels: [],
    },
```

### `trafficCessationAlertConfig: { }`

This configuration allows each aggregation-set to be filtered using a selectorHash.

The key for the configuration hash is the `AggregationSet` `id` attribute, as defined in `metrics-catalog/aggregation-sets.libsonnet`, and the value is the selector hash.

Any omitted values will be enabled by default (with the default hash).

```jsonnet
    server: {
      trafficCessationAlertConfig: {
        regional_component: { region: "us-east1" }, // Only check region us-east1 for traffic cessation issues
        component_node: false // Ignore any traffic cessation issues on a single node.
      },
      userImpacting: false,
      requestRate: metricsCatalog.rateMetric(
        counter='gitaly_service_client_requests_total',
      ),
      significantLabels: [],
    },
```
