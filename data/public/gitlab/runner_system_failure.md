# HostedRunnersServiceCiRunnerJobsErrorSLOViolationSingleRunnerManager

This alert indicates that jobs are failing due to runner system failures. These failures are often related to the runner infrastructure, fleeting plugin, auto-scaling issues, or network problems. The **Failed Job Errors** chart can be used to confirm the issue.

## Possible Causes

- Runner infrastructure issues
- Docker/fleeting auto-scaling problems
- Network-related failures

## General Troubleshooting Steps

1. **Check AWS network status**
2. **Check AWS auto-scaling activity status**
     - Review the status of AWS fleeting nodes to ensure they are scaling correctly and not causing failures.
3. **Review GitLab Runner logs in OpenSearch**
     - Use the OpenSearch dashboard to examine `gitlab-runner` logs for any system failures or errors.
     - **If OpenSearch logging is not enabled** (e.g., for customers without OpenSearch logging): SSM into the runner manager instance and check the logs directly via the command:

     ```bash
     sudo journalctl -u gitlab-runner
     ```

If you find relevant information in the logs, this doc could help you resolve specific issues:
     [GitLab Runner troubleshooting](https://docs.gitlab.com/runner/faq/#general-troubleshooting-tipsd)

## Using Grafana Explore

Use the [Explore](https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/#access-explore) function on the customer's Grafana instance to see the specific data which has caused this alert. These queries might help get you started:

```
# Per-second rate of failed jobs due to runner system failures over the last 5 minutes for a specific shard
rate(gitlab_runner_failed_jobs_total{failure_reason="runner_system_failure",job="hosted-runners-prometheus-agent",shard="<shard>"}[5m])

# Error ratio for CI runner jobs over the last 1 hour for a specific shard
gitlab_component_shard_errors:ratio_1h{component="ci_runner_jobs",type="hosted-runners",shard="<shard>"}

# Error ratio for CI runner jobs over the last 5 minutes for a specific shard
gitlab_component_shard_errors:ratio_5m{component="ci_runner_jobs",type="hosted-runners",shard="<shard>"}

# Error ratio for CI runner jobs over the last 6 hours for a specific shard
gitlab_component_shard_errors:ratio_6h{component="ci_runner_jobs",type="hosted-runners",shard="<shard>"}

# Error ratio for CI runner jobs over the last 30 minutes for a specific shard
gitlab_component_shard_errors:ratio_30m{component="ci_runner_jobs",type="hosted-runners",shard="<shard>"}
```
