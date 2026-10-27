# IMDS Throttling

GitLab Runner relies on IMDS to obtain short-lived AWS credentials for S3 cache access. When IMDS was throttled, those credential requests fail, causing failed cache retrieval attempts. If the affected jobs were configured to fail when cache is missing, this results in a high rate of job failures.

## Symptoms

IMDS Throttling might be suspected if

- If the customer is reporting unexpected, transient cache related job failures.
- There is a sudden, unexpected increase in script failures disproportionate to the increase in running jobs as seen on the customers [Hosted Runners Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard)

It is also possible that if IMDS throttling continues long enough and there is an influx of constantly retrying jobs, more than what the system can handle, you might also get paged for HostedRunnersServiceCiRunnerJobsApdexSLOViolationSingleRunnerManager

At its very worst IMDS Throttling could cause a Sev1 incident

### Verification of cause

If you are experiencing cache related IMDS throttling, you will see an excessive number of (`json.msg: *no EC2 IMDS role found*` OR `json.err: *no EC2 IMDS role found*`) AND `fluent_d: *{shard}-manager-logs` in the [Opensearch logs](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch) for a customer.

It is also worth briefly looking over all `fluent_d: *{shard}-manager-logs` and `json.level: error` in the [Opensearch logs](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch) for a customer during the problem period, just in case the message is formatted differently after recent observability improvements.

Alternatively you could run the monitoring commands AWS shared `sudo ss -tnp dst 169.254.169.254` and `sudo tcpdump -i any host 169.254.169.254 -nn -c 500` [on the affected Runner Manager](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#valuable-troubleshooting-commands-to-run-for-a-gitlab-runner-inside-a-container-on-a-runner-manager) to track active connections and traffic patterns.

You can also investigate these metrics to get a deeper understanding of what is going on.

| Metric | Type | Description | Gitlab-Runner Binary Availability |
| --- | --- | --- | --- |
| gitlab_runner_cache_s3_assume_role_requests_in_flight | Gauge | Number of AssumeRole requests to AWS STS in progress. | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_wait_seconds | Histogram | Wait time to acquire a concurrency slot before issuing an AssumeRole request. | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_duration_seconds | Histogram | Duration of AssumeRole API calls to AWS STS. | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_cache_hits_total | Counter | Number of AssumeRole credential cache hits (STS call avoided). | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_cache_misses_total | Counter | Number of AssumeRole credential cache misses (This is also a count of the STS calls for cache credentials that were made). | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_cached_credentials | Gauge | Number of AssumeRole credentials held in the in-memory LRU cache. | v18.11.0 onwards |
| gitlab_runner_cache_s3_assume_role_failures_total | Counter | Number of AssumeRole requests which failed. | v19.0.0 onwards |

## Short term mitigation

1. Add this to the Runner Stacks [RUNNER_MODEL Overrides in Switchboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#get-the-runner-model-of-a-runner-shard-via-switchboard) to switch that runner away from role based authentication (which relies on IMDS) to using instead static user based authentication

```
{
...
  "stack": {
    "cache": {
      "bucketAuthType": "user-based"
    },
    ...
  }
...
}
```

1. Run `hosted_runner_deploy` via Switchboard to [redeploy](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#immediately-applying-changes)

The IMDS errors should disappear as soon as the provision job has completed.

## Long term remediation

Changes to how credentials are gathered for IAM Roles in gitlab-runner v18.11 should greatly reduce the likelihood of IMDS Throttling on connections to an s3 cache.
