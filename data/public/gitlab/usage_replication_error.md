# Troubleshooting HostedRunnersLoggingServiceUsageReplicationErrorSLOViolation

When the `HostedRunnersLoggingServiceUsageReplicationErrorSLOViolation` alert is triggered, it indicates that replication has stopped for some reason. This issue is **not** related to the runner account and should be investigated from the **tenant account** perspective.

## Possible Causes

The primary reasons for replication failure are:

1. **Permission issues** – The required IAM roles or policies may be misconfigured.
2. **Underlying network issues** – Connectivity problems between AWS services could prevent replication.

## Steps to Investigate

1. Check the status of the last objects in the S3 bucket to determine when replication stopped.
2. Verify the replication configuration in AWS S3 to identify potential permission or network issues.

## Resolution Steps

AWS does not automatically retry replication for pending objects once a failure occurs. You must manually replicate the objects by following these steps:

1. **Break the glass** to access the tenant infrastructure.
2. **Navigate to the S3 bucket**.
3. **Go to Batch Operations** and create a new job.
4. **Under Manifest**, select `Create manifest using S3 Replication configuration` to identify unreplicated objects.
5. **Replication configuration source bucket** should be in the same account, and choose the bucket name with format `{customer_name}-hosted-runner-usage`.
6. **Leave the filter as it is**.
7. **For the replication status**, choose `failed`.
8. **Check the Save Batch Operations manifest**.
9. **The location for batch manifest** should be `{customer_name}-hosted-runner-usage-report` and leave the rest as it is.
10. Click **Next**.

11. **For Operation type**, choose `Replicate`.

12. Click **Next**.

13. **For completion report bucket**, choose the same bucket selected in step 9, and the scope should be **all tasks**.

14. **For IAM permission**, open the search bar and filter by `{customer_name}-runner-s3-replication-role`.

15. Click **Next** and **Create job**.

It takes a few minutes to prepare the job. Wait until the job is ready and has the status `Awaiting your confirmation to run`. Click on it and **run the job**. Wait for the job to finish.

After it completes successfully:

- Check the report bucket and find the job report by job ID.
- Review the manifest to ensure all replications were successful.
- Check the job failed rate at the end, which should be **zero**.

## Using Grafana Explore

Use the [Explore](https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/#access-explore) function on the customer's Grafana instance to see the specific data which has caused this alert. These queries might help get you started:

```
# Average number of failed S3 replication operations over 5 minutes
avg_over_time(aws_s3_operations_failed_replication_sum[5m])

# Error ratio for usage replication over the last 1 hour
gitlab_component_errors:ratio_1h{component="usage_replication",type="hosted-runners-logging"}

# Error ratio for usage replication over the last 5 minutes
gitlab_component_errors:ratio_5m{component="usage_replication",type="hosted-runners-logging"}

# Error ratio for usage replication over the last 6 hours
gitlab_component_errors:ratio_6h{component="usage_replication",type="hosted-runners-logging"}

# Error ratio for usage replication over the last 30 minutes
gitlab_component_errors:ratio_30m{component="usage_replication",type="hosted-runners-logging"}
```
