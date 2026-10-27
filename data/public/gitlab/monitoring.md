# NATS monitoring

Dashboard for NATS servers can be found [here](https://dashboards.gitlab.net/goto/ef37nvqj8xybkb?orgId=1).

Available servers can also be verified by the following promQL query:

```promql

(count by(type, env) (nats_healthz_js_enabled_only_status_value{value="ok"}) == bool count by(type, env) (nats_healthz_js_enabled_only_status_value) ) == 1

```

There is also a [NATS SLI dashboard](https://dashboards.gitlab.net/goto/HU9k1hjNg?orgId=1) that covers the rate and errors metrics for requests to NATS servers. Slow consumers or redelivered messages to consumers are current indicators of errors here.

NATS monitoring [docs](https://docs.nats.io/running-a-nats-service/nats_admin/monitoring) are a good reference to see other available metrics from its system. We rely on NATS [prom exporter](https://github.com/nats-io/prometheus-nats-exporter) to export this into our environment.
