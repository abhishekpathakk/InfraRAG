# Troubleshooting HostedRunnersLoggingServiceUsageLogsErrorSLOViolation

This document outlines the steps to troubleshoot issues related to the alert `HostedRunnersLoggingServiceUsageLogsErrorSLOViolation`, which indicates that the Fluentd S3 plugin is unable to forward logs to the tenant S3 bucket.

## Troubleshooting Steps

1. **Verify the Alert:** Check the alert details and hosted runner logging dashboard for any additional context or metadata.
2. **Break the Glass:** Break the glass to obtain temporary access to the customer runner account.
3. Navigate to **AWS CloudWatch**
4. **Locate the Fluentd Logs:** Navigate to the log group associated with Fluentd ( {runner_name}/ecs-logs)

- Open the relevant log streams (ecs-fluentd within this log group.

5. **Filter Logs for S3-Related Errors**

- Use the CloudWatch log filtering feature to search for the keyword `s3`.
- Review all error entries that pertain to the S3 plugin.

6. **Analyze the Errors**

- Identify the specific error messages related to the S3 plugin.
- Common issues to look for:
- Authentication or permission errors
- Network timeouts or connectivity issues
- Determine if any recent changes or deployments might have affected the configuration.

## Using Grafana Explore

Use the [Explore](https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/#access-explore) function on the customer's Grafana instance to see the specific data which has caused this alert. These queries might help get you started:

```
# Per-second rate of Fluentd S3 plugin output errors over the last 5 minutes for a specific shard
rate(fluentd_output_status_num_errors{job="hosted-runners-fluentd-agent",plugin="s3",shard="<shard>"}[5m])

# Error ratio for usage logs over the last 1 hour for a specific shard
gitlab_component_shard_errors:ratio_1h{component="usage_logs",type="hosted-runners-logging",shard="<shard>"}

# Error ratio for usage logs over the last 5 minutes for a specific shard
gitlab_component_shard_errors:ratio_5m{component="usage_logs",type="hosted-runners-logging",shard="<shard>"}

# Error ratio for usage logs over the last 6 hours for a specific shard
gitlab_component_shard_errors:ratio_6h{component="usage_logs",type="hosted-runners-logging",shard="<shard>"}

# Error ratio for usage logs over the last 30 minutes for a specific shard
gitlab_component_shard_errors:ratio_30m{component="usage_logs",type="hosted-runners-logging",shard="<shard>"}
```
