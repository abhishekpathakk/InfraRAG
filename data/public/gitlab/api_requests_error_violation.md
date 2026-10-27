# HostedRunnersServiceApiRequestsErrorSLOViolationSingleRunnerManager

This alert triggers when the Hosted runners API is returning too many errors (5xx status codes) on a single shard. There are two alert rules, and either of them will fire this alert.

Rule 1 (1-hour window): Fires if error rate exceeds 1.44% for both the last hour AND last 5 minutes, with sustained traffic.
Rule 2 (6-hour window): Fires if error rate exceeds 0.6% for both the last 6 hours AND last 30 minutes, with sustained traffic.

**General Troubleshooting Steps**

1. Take a look at the [Hosted Runner Dashboards](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#dashboards) on the Customers Grafana Instance and notice any anomalies in the metrics
2. Use the [Explore](https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/#access-explore) Function on the Customers Grafana Instance to see the specific data which has caused this alert. These queries might help get you started.

```
# Per-second rate of API requests with 5xx status codes over the last 5 minutes for a specific shard
rate(gitlab_runner_api_request_statuses_total{job="hosted-runners-prometheus-agent",shard="{{ brokenshard }}",status=~"5.."}[5m])

# Error ratio for API requests over the last 6 hours for a specific shard
gitlab_component_shard_errors:ratio_6h{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Error ratio for API requests over the last 30 minutes for a specific shard
gitlab_component_shard_errors:ratio_30m{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Error ratio for API requests over the last 1 hour for a specific shard
gitlab_component_shard_errors:ratio_1h{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Error ratio for API requests over the last 5 minutes for a specific shard
gitlab_component_shard_errors:ratio_5m{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Rate of API request operations per second over the last 6 hours for a specific shard
gitlab_component_shard_ops:rate_6h{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Rate of API request operations per second over the last 30 minutes for a specific shard
gitlab_component_shard_ops:rate_30m{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Rate of API request operations per second over the last 1 hour for a specific shard
gitlab_component_shard_ops:rate_1h{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}

# Rate of API request operations per second over the last 5 minutes for a specific shard
gitlab_component_shard_ops:rate_5m{component="api_requests",type="hosted-runners",shard="{{ brokenshard }}"}
```

3. Look at [the Customers logs in Opensearch](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch) and try to find logs for the failed api requests. Here are some filters which could get you started.

```
fluentd_tag: "cloudwatch.kinesis.{{ brokenshard }}-manager-logs" AND json.level: "error"

fluentd_tag: "cloudwatch.kinesis.{{ brokenshard }}-manager-logs" AND json.status: 500

fluentd_tag: "cloudwatch.kinesis.{{ brokenshard }}-fleeting-logs" AND message: "level=error"
```
