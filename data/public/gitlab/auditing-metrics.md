# Auditing Metrics

**Warning:** Running these commands can put unnecessary pressure on our metrics backend and should be used sparingly and with caution. You shouldn't be running these commands unless you really need to.

[Mimirtool](https://grafana.com/docs/mimir/latest/manage/tools/mimirtool/#analyze) is a CLI tool that can be used to manage and gather information on Mimir, and which we can utilize to audit our metrics.

In the following example we will use Mimirtool to identify which metrics are, and are not being used.

1. Set the Grafana API key. For example, an API key stored in 1Password as a password item.

   ```bash
   export GRAFANA_API_KEY=$(op item get "<grafana_api_token_name>" --fields label=password)
   ```

1. Set the address of the Grafana instance.

   ```bash
   export GRAFANA_ADDRESS=https://dashboards.gitlab.net
   ```

1. Set the path to the Runbooks repository.

   ```bash
   export RUNBOOKS_DIR=<path_to_runbooks_repository>
   ```

1. Create a directory to keep all the rules in a single place for simplicity.

   ```bash
   export RULES_DIR=<rules_dir> && mkdir -p $RULES_DIR
   ```

1. Copy the rules from the Runbooks repository to our newly created directory.

   ```bash
   find "${RUNBOOKS_DIR}/mimir-rules" "${RUNBOOKS_DIR}/legacy-prometheus-rules" -type f \( -name "*.yml" -o -name "*.yaml" \) | xargs -I {} cp {} "${RULES_DIR}/"
   ```

1. You may need to merge files with duplicate namespaces due to this [issue](https://github.com/grafana/mimir/issues/6748). Here is an example with two files that are both using the `alerts` namespace.

   ```bash
   yq eval-all '. as $item ireduce ({}; . *+ $item)' "${RULES_DIR}/alerts.yaml" "${RULES_DIR}/alerts.yml" > "${RULES_DIR}/alerts-merged.yml" && rm "${RULES_DIR}/alerts.yaml" "${RULES_DIR}/alerts.yml"
   ```

1. Extract the Prometheus metrics used in the queries in our Grafana dashboards into a file called `metrics-in-grafana.json`.

   ```bash
   mimirtool analyze grafana
   ```

1. Extract the Prometheus metrics used in the queries in the rules directory we created into a file called `metrics-in-ruler.json.`

   ```bash
   mimirtool analyze rule-file $RULES_DIR/*
   ```

1. Before we connect to the Mimir Query Frontend you may need to setup Port Forwarding to your Kubernetes cluster. We will be connecting to the `pre` cluster.

   ```bash
   glsh kube use-cluster pre && kubectl port-forward -n mimir svc/mimir-query-frontend 8080:8080
   ```

1. Now we can compare the metrics used in both the `metrics-in-grafana.json` and `metrics-in-ruler.json` with the series in the `metamonitoring` Tenant in Mimir and create a file called `prometheus-metrics.json` this will tell us which metrics are used and unused. Substitute `metamonitoring` in the following command if you are interested in another tenant.

   ```bash
   mimirtool analyze prometheus --address="http://127.0.0.1:8080" --id=metamonitoring --prometheus-http-prefix=/prometheus
   ```

1. To make it a little easier to see which metrics are used we can parse the results that are stored in `prometheus-metrics.json` into two new files.

   ```bash
   jq -r ".in_use_metric_counts[].metric" prometheus-metrics.json | sort > used-metrics.txt && jq -r ".additional_metric_counts[].metric" prometheus-metrics.json | sort > unused-metrics.txt
   ```
