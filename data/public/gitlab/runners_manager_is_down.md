# HostedRunnersServiceRunnerManagerDown

This alert indicates that a GitLab Runner Manager (`{{ $labels.runner_manager }}`, shard `{{ $labels.shard }}`) in a hosted-runners stack (`{{ $labels.stack }}`) has been unhealthy for more than 5 minutes. It fires in one of two situations:

- the host is alive (node exporter is scraped) but the runner metrics endpoint is not: the runner process crashed, hung, or its metrics listener is blocked
- the runner process is up but has made no GitLab API requests for 10 minutes: a healthy runner polls for jobs continuously, so this points at a network path, DNS, or PrivateLink failure between the manager and the instance

Job capacity for the stack is reduced while a manager is down. If every manager in the stack fires at once, new pipeline jobs cannot be picked up until at least one recovers. Jobs that were already running when the manager disappeared need their outcome checked separately, after recovery.

## Blue/green rotations

A rotation drains the old shard before destroying it (`deployer shutdown` -> `wait-terminated` -> `down`). During the drain the runner stops polling for jobs while still serving metrics, and after it exits the host stays up until Terraform destroys it; both states would otherwise match the alert. Two exclusions keep rotations silent:

- The "no API requests" clause ignores managers currently reporting `gitlab_runner_process_state_info{state="graceful-shutdown"}` (or `forceful-shutdown`): a draining runner stops polling for jobs by design.
- The "host alive, runner gone" clause ignores managers whose stack has `running` managers in another shard. This covers the window between the runner exiting and Terraform destroying the host, including idle managers whose graceful shutdown completes within one scrape interval. It only applies while two shards coexist; in steady state a stack has one shard.

If this alert fires for a shard that is being rotated, the manager lost its runner process before the new shard was `running` (a crash, not a drain). Note that while a rotation is stuck with both shards present, a crashed runner on either shard is not paged by the host-alive clause; the "no API requests" clause still applies to both.

## Restore the runner first

Do this before reading any logs. Diagnosis can wait; the tenant's CI cannot.

1. Identify the affected runner. Use the numeric GitLab runner database ID in the alert's
   `runner_id` label (for example, `688644`), not the runner registration token, runner
   name, or shard ID. The alert also carries `tenant_id` and `region`. The `stack` label is
   sometimes empty, so do not rely on it alone. Cross-check the runner against the hosted
   runner dashboard for the tenant.
2. In Switchboard, run the `hosted_runner_deploy` task for that runner.
3. Confirm recovery: the runner's Prometheus target returns, jobs start being picked up
   again, and the alert resolves.

If the deploy does not bring the runner back, work through the causes below.

## Steps to Troubleshoot

1. **Check if the Customer Deleted the Runner**: The customer might have intentionally or unintentionally deleted the runner from the admin side. To confirm:
   1. Access the GitLab Rails console.
   2. Run the following command (replace $RUNNER_ID with the actual runner ID from hosted runner dashboard):

      ```ruby
      Ci::RunnerManager.where(runner_id: $RUNNER_ID)
      ```

   3. If the command returns `null`, it means the customer has deleted the runner. In this case:
      - **Action**: Communicate with the customer to confirm the reason for deletion.
      - **Fix**: The best option is to deprovision the runner and create a new one via the Switchboard UI, which will also generate a new token.

2. **The EC2 node hosting the Runner Manager is down or absent**: This is more likely be related to the tenant maintenance window, where a new VM for the Runner Manager is being provisioned. If the provisioning takes more than 5 minutes, the alert will be triggered. If the issue isn't related to the maintenance window simply running another provision job will create new runner manager.

3. **The Runner Manager encountered issues**: Check the tenant's OpenSearch logs. Filter the manager logs using the following Fluentd tag and look for errors around the last manager record.

   ```text
   fluentd_tag: cloudwatch.kinesis.<runner-name>-manager-logs
   ```

## Using Grafana Explore

Use the [Explore](https://grafana.com/docs/grafana/latest/visualizations/explore/get-started-with-explore/#access-explore) function on the customer's Grafana instance to see the specific data which has caused this alert. These queries might help get you started:

```
# Rate of API requests operations per second over the last 5 minutes for a specific shard
gitlab_component_shard_ops:rate_5m{component="api_requests",type="hosted-runners",shard="<shard>"}

# Per-second rate of API request statuses over the last 5 minutes for a specific shard
rate(gitlab_runner_api_request_statuses_total{job="hosted-runners-prometheus-agent",shard="<shard>"}[5m])
```

## Post-recovery cleanup and impact analysis

Once the runner is back, you may be asked whether any jobs were lost. This section
produces an *estimate* of the jobs that need looking at. It cannot certify loss. Read
the limits before quoting any number.

### Why the manager's own logs cannot answer this

A dead manager cannot report a final job status or increment
`gitlab_runner_failed_jobs_total`, so the absence of a failure signal proves nothing.
Worse, the manager's last per-job event can lag GitLab. Manager VM logs can also be buffered
and never shipped. Build the job list from the GitLab side instead.

### Find the jobs the runner was handed

Query the tenant's Rails and workhorse logs in OpenSearch. Choose a window that starts
well before the manager stopped and ends at the last runner manager log record.

In the tenant's OpenSearch Dashboard, open **Dev Tools**, replace each angle-bracketed
placeholder below, and run the request. The returned job IDs are in
`aggregations.jobs.buckets[].key`.

```console
POST gitlab-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "range": { "@timestamp": { "gte": "<window-start>", "lte": "<manager-last-record>" } } },
        { "term": { "meta.client_id.keyword": "runner/<numeric-runner-id>" } },
        { "term": { "path.keyword": "/api/v4/jobs/request" } },
        { "term": { "status": 201 } }
      ]
    }
  },
  "aggs": { "jobs": { "terms": { "field": "meta.job_id", "size": 1000 } } }
}
```

Two things to watch. The count depends on `<window-start>`: a job picked up earlier and
still running will not appear, so state the window whenever you quote a number. And
`"size": 1000` caps the buckets, so check `sum_other_doc_count` in the response and page
the query if it is non-zero.

### Check which of those reached a terminal state

For the same job IDs, look for a later terminal marker. `Ci::BuildFinishedWorker` is the
one to use. Set `<terminal-search-end>` to the current UTC time when you run this query;
it is the latest point at which you looked for a terminal marker. The matching job IDs are
again in `aggregations.jobs.buckets[].key`.

```console
POST gitlab-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "range": { "@timestamp": { "gte": "<window-start>", "lte": "<terminal-search-end>" } } },
        { "terms": { "meta.job_id": [ "<job ids from the previous query>" ] } },
        { "term": { "meta.caller_id.keyword": "Ci::BuildFinishedWorker" } }
      ]
    }
  },
  "aggs": { "jobs": { "terms": { "field": "meta.job_id", "size": 1000 } } }
}
```

### Check how often the terminal marker is present

The terminal marker is not perfectly complete. Before reporting anything, measure how
often it appears for jobs known to have finished before the manager died: use
`manager.msg: "Job succeeded"` and `manager.msg: "Job failed: exit code 1"`, then check
what fraction of those job IDs also have `Ci::BuildFinishedWorker`. This fraction is the
marker coverage for this tenant and time window.

On INC-12725 that came back 363/363 successes and 1/1 failure over 19:40-19:45Z, but
559/564 successes over the wider 19:40-19:46:52Z window. Five jobs that definitely
succeeded had no terminal marker. The reason was not established; a missing marker is
therefore a strong signal and nothing more.

### What you can report

- the number of jobs the runner was handed, with the window you used
- how many of those have a terminal marker
- how many have status unknown because no terminal marker was found
- the terminal-marker coverage measured above, so the reader can judge the false-negative
  rate

Do not describe the remainder as lost, dropped, or orphaned on this evidence. Retries get
a new job ID, so a later job in the same pipeline does not settle what happened to the
original. Certifying the outcome needs the tenant's Rails console or database, which is
not yet documented here.
