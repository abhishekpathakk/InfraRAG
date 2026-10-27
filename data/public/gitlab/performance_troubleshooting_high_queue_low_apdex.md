# Performance Troubleshooting: Low Apdex & High Queue Duration on Dedicated Hosted Runners (DHR)

This runbook is intended as a comprehensive primer on Performance Troubleshooting: Low Apdex & High Queue Duration on Dedicated Hosted Runners (DHR).

Apdex on DHR is determined by the ratio of jobs breaching the acceptable queuing threshold duration of 2 minutes versus the number of jobs that don't. This runbook is primarily focused on troubleshooting low apdex and high average queuing duration.

## Tools Required

1. Access to [Grafana](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch) for the Dedicated Hosted Runner Customer.
2. Access to [Opensearch](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch) for the Dedicated Hosted Runner Customer

## Am I experiencing a Performance Problem on DHR?

If you are experiencing a Performance Problem on DHR you will likely see the following symptoms on the [Hosted Runner Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard) for that customer and runner stack.

1. Increasing `Average duration of queuing` (specifically a sustained value over the acceptable queuing threshold duration of 2 minutes), increased `Pending jobs queue size`, `Pending job queue duration histogram`, `Acceptable job queuing duration exceeded` and `Jobs queuing failure rate`.
1. A drop in `hosted-runners Service Apdex` for either the `ci_runner_jobs` or `pending_builds` components. Note these two metrics are both a factor of how many jobs exceed the acceptable queuing threshold duration of 2 minutes.
1. You may have been paged for `HostedRunnersServiceCiRunnerJobsApdexSLOViolationSingleRunnerManager`, `HostedRunnersServicePendingBuildsApdexSLOViolationSingleRunnerManager`, and/or `component_saturation_slo_out_of_bounds:pending_builds`

Note that even if you were paged for a specific runner stack, it is worthwhile to briefly check other runner stacks as well as often problems are spread across multiple runner stacks.

## Making a timeline

It is highly recommended to make a brief timeline during a performance incident in order to clarify the order of events and reveals the difference between causes and consequences. It helps determine what might be the bottleneck, as opposed to what might just be an unlucky flow on effect.

1. Open the [Hosted Runners Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard) and note when `Apdex` first began to drop on the relevant runner stack.
1. Scroll down to the `Pending Jobs` section and note when those graphs began to spike.
1. Notice any other sudden changes on any of the other graphs on the dashboard and add those to your timeline.
1. Identify if any recent code, configuration changes, or infrastructure updates have occurred, and add those to the timeline if relevant.
1. Post your timeline along with a shortened, timebound link to the relevant dashboard in the incident channel. You may want to also screenshot key moments.

## Checking known common bottlenecks

There are a number of known common bottlenecks in Dedicated Hosted Runners. You might choose to rapidly check if you are likely experiencing any of these.

1. [scaleMax](#scalemax)
1. [scaleFactor](#scalefactor)
1. [requestConcurrency](#requestconcurrency)

### scaleMax

`scaleMax` in a runner model is equivalent to [concurrent](https://docs.gitlab.com/runner/configuration/advanced-configuration/#:~:text=Description-,concurrent,-Limits%20how%20many) and [max_instances](https://docs.gitlab.com/runner/configuration/advanced-configuration/#:~:text=scheduled%20for%20removal.-,max_instances,-The%20maximum%20number) in the runners `config.toml`. It represents both the maximum number of ephemeral virtual machines that can exist simultaneously, and the maximum number of jobs that can run concurrently.

#### Symptoms of `scaleMax` saturation

If your performance problem is due to saturation of `scaleMax` you will see the following symptoms on the [Hosted Runners Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard).

1. The symptoms already explained in [Am I experiencing a Performance Problem on DHR?](#am-i-experiencing-a-performance-problem-on-dhr)
1. `Runner saturation of concurrent by shard` will approach 80%. Note, because some fleeting instances will usually be in either the creating or destroying state, `Runner saturation of concurrent by shard` is unlikely to ever reach 100%
1. `Fleeting instances saturation` AND `Taskscaler tasks saturation` will approach 100%. If `Fleeting instances saturation` approaches 100% BUT `Taskscaler tasks saturation` DOES NOT, this is not a `scaleMax` bottleneck!
1. `Taskscaler operations failure` will see a spike in `reserve_iop_capacity_failure` errors.
1. `Worker processing failures rate` will see a spike in `no_free_executor` errors.

#### Increasing scaleMax

1. [Open Runner Model Overrides](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#get-the-runner-model-of-a-runner-shard-via-switchboard)
2. Add this to Runner Model Overrides

```
{
  "stack": {
    ...
    "scaleMax": 100, # example number, use your best judgement
  }
}
```

3. Run the `hosted_runner_deploy task` for that Runner Stack to [immediately apply changes](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#immediately-applying-changes).

> [!warning]
> As of April 2026, we have not tested `scaleMax` on a single runner stack above 400. There may be negative performance implications of a `scaleMax` above 400, specifically, pod level OOMKills for memory saturation on the tenant's Registry.

### scaleFactor

`scaleFactor` in a runner model is equivalent to [scale_factor](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-runnersautoscalerpolicy-sections:~:text=it%20is%20terminated.-,scale_factor,-The%20target%20idle) in the runners `config.toml`.
It represents how fast new virtual machines are being created to respond to a spike in jobs being added to the queue.

#### Symptoms of `scaleFactor` bottleneck

A `scaleFactor` bottleneck means that new virtual machines are not being created fast enough to keep up with a sudden spike in jobs added to the queue.

If your performance problem is due to low `scaleFactor` you will see the following symptoms on the [Hosted Runners Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard).

1. The symptoms already explained in [Am I experiencing a Performance Problem on DHR?](#am-i-experiencing-a-performance-problem-on-dhr)
1. `Taskscaler desired instances` will be positive
1. `Taskscaler operations failure` will see a spike in `reserve_available_capacity_failure` errors but NOT `reserve_iop_capacity_failure` errors.
1. `Fleeting instances saturation` will NOT be near 100%. If `Fleeting instances saturation` is already 100%, you are NOT experiencing a `scaleFactor` bottleneck.
1. `Worker processing failures rate` will see a spike in `no_free_executor` errors.
1. `Fleeting instance operations rate` may see a spike in `create` operations
1. `Taskscaler scale operations rate` may see a spike in `up` operations

#### Increasing `scaleFactor`

We can adjust `scaleFactor` either for the entire runner stack at all times of day or only for a specific known high usage time of day or week. Note that increasing `scaleFactor` is expensive because it increases the number of idle machines for each machine in use non-linearly.

If there is a known time of spiky load when we want to have a higher `scaleFactor`, this is possible using autoscaling polices.
If autoscaling policies are already configured for a specific Runner Stack, it is wise to assume this was done for a reason and to continue to use autoscaling policies to set `scaleFactor` at a specific time or day.

#### Increasing `scaleFactor` for a specific time or day

We can change `scaleFactor` for a specific time or day using `autoscalingPolicies`, equivalent to a [\[\[runners.autoscaler.policy\]\]](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-runnersautoscalerpolicy-sections)

1. [Open Runner Model Overrides](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#get-the-runner-model-of-a-runner-shard-via-switchboard)
2. Add this to Runner Model Overrides

```
{
  "stack": {
    ...
    "autoscalingPolicies": [ # example numbers, use your best judgement.
      {
        "periods": [
          "* * * * *" # first policy becomes default, so must apply to all time periods. This is cron job.
        ],
        "idleTime": "20m0s",
        "scaleMin": 4,
        "timezone": "UTC", # you can change this to the customers timezone if it makes reasoning easier using the Linux tzdata (timezone data) format
        "scaleFactor": 5, # set sensible defaults for most times, you can copy these from the existing values in Runner Model if you like.
        "scaleFactorLimit": 0
      },
      {
        "periods": [
          "* * * * 1" # specify the time or day that you need a higher scaleFactor for
        ],
        "idleTime": "20m0s",
        "scaleMin": 4,
        "timezone": "UTC", # you can change this to the customers timezone if it makes reasoning easier using the Linux tzdata (timezone data) format
        "scaleFactor": 10, # example number, use your best judgement
        "scaleFactorLimit": 0
      }
    ]
  }
}
```

An astute observer will notice that `scaleMin`, `idle_time` etc can also be changed using `autoscalerPolicies` should that become necessary.

3. Run the `hosted_runner_deploy task` for that Runner Stack to [immediately apply changes](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#immediately-applying-changes).

#### Increasing scaleFactor for all times and days

Only do this is if the Runner Stack does not already have [autoscalingPolicies](#increasing-scalefactor-for-a-specific-time-or-day) configured.

1. [Open Runner Model Overrides](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#get-the-runner-model-of-a-runner-shard-via-switchboard)
2. Add this to Runner Model Overrides

```
{
  "stack": {
    ...
    "scaleFactor": 7, # example number, use your best judgement
  }
}
```

3. Run the `hosted_runner_deploy task` for that Runner Stack to [immediately apply changes](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#immediately-applying-changes).

### `requestConcurrency`

`requestConcurrency` in the Runner Model is equivalent to [`request_concurrency`](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-runnersautoscalerpolicy-sections:~:text=overwrite%20environment%20variables.-,request_concurrency,-Limit%20number%20of) in the runners config.toml. It is the maximum number of of requests for new jobs from GitLab API that can exist concurrently.

Note DHR does use the `FF_USE_ADAPTIVE_REQUEST_CONCURRENCY` feature flag to automatically adjust request_concurrency based on workload - however these adjustments are only ever downwards from the hard cap of the configured `requestConcurrency` in the Runner Model. For example, a `requestConcurrency = 5` means that the number of concurrent requests to the API will dynamically adjust between 1 and 5 depending on the rate of successful job requests.

An appropriately tuned `requestConcurrency` prevents the runner stack from overloading the Gitlab API with `request_job` requests during times of low load.
An inappropriately low `requestConcurrency` interacts with multiple other variables to provide a throughput limit on how many jobs can be requested per minute from the Gitlab API.

Maximum jobs that can be requested per minute for a runner stack:

```math
(\text{request_concurrency} * \frac{60}{\max(\text{check_interval}, \text{request_duration})}) * \text{count of runner managers}
```

#### Symptoms of `requestConcurrency` saturation

If your performance problem is due to low `requestConcurrency` you will see the following symptoms on the [Hosted Runners Overview Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#hosted-runners-overview-dashboard).

1. The symptoms already explained in [Am I experiencing a Performance Problem on DHR?](#am-i-experiencing-a-performance-problem-on-dhr)
1. There wil be a spike in `Request concurrency exceeded`
1. `Request concurrency` `used limit` will be equal to the `hard limit` for a sustained period of time.
1. There will be a very high `Taskscaler idle ratio` alongside a low `Taskscaler tasks saturation` while `Fleeting instances saturation` approaches 100%

#### Increasing requestConcurrency

1. [Open Runner Model Overrides](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#get-the-runner-model-of-a-runner-shard-via-switchboard)
2. Add this to Runner Model Overrides

```
{
  "stack": {
    ...
    "requestConcurrency": 12 # example number, use your best judgement
  }
}
```

## Checking the Opensearch Logs

You can check the logs in [Opensearch](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch).

## Deeper Understanding of specific difficult graphs and metrics from the Hosted Runners Overview Dashboard

### Global count of pending builds vs Pending jobs queue size

`Global count of pending builds` graph uses `ci_pending_builds` metric and returns for the entire GitLab instance.
`Pending jobs queue size` graph uses `gitlab_runner_job_queue_size` and can be divided by stack and/or shard.

If `Global count of pending builds` spikes but `Pending jobs queue size` does not, some other runner - maybe the customer's self hosted runner, maybe a runner filtered out by the current dashboard settings - is dequeuing those jobs.

### Runner saturation of limit by shard

As of April 2026 this graph will always show 0 as we have no need to configure limits on DHR. This 0 is intentional.

### Jobs queuing failure rate

This graph sometimes causes confusion so I want to clarify - it is the rate of jobs where the acceptable job queuing duration of 2 minutes was exceeded. The jobs did not actually fail and were likely still processed. The only failure was the failure to be picked up off the queue in a timely manner.

You can see the same data as a count rather than a rate in `Acceptable job queuing duration exceeded`.

### Runner saturation of concurrent by shard vs Fleeting instances saturation vs Taskscaler tasks saturation

`Runner saturation of concurrent by shard` graphs shows how many jobs are running right now out of the `concurrent` allowed.
`Fleeting instances saturation` graphs how many ephemeral virtual machines exist in running, creating or deleting states out of the `max_instances` allowed. It answers "What % of my allowed ephmeral VMs are provisioned?"
`Taskscaler tasks saturation` graphs how many slots on a ephemeral virtual machine are not idle or reserved out of the total `max_instances` allowed. It answers "What % of my total job capacity is actively being used to process jobs?"

As already discussed both `max_instances` and `concurrent` are controlled by `scaleMax`

Despite this, there are many reasons for these graphs to differ

1. Perhaps we have more ephemeral virtual machines running than is required and they are sitting idle.
1. Perhaps we are taking a long time to create or delete ephermal virtual machines, or acquire or begin tasks on virtual machines.
1. Perhaps something is blocking us from picking up new jobs from the queue.

### Taskscaler tasks

On the `Taskscaler tasks` graph, a `task` is just a slot on an ephemeral virtual machine which should in theory be able to execute a job. We only use each ephermeral virtual machine once, but a task can be in a different state from its wider ephemeral virtual machine fleeting instance.

* Idle — Slots that are available and ready to accept a new task. It would be an enormous red flag that something is preventing a runner stack from executing jobs if you saw idle tasks during a performance incident.
* Pending — The number of `Acquire()` calls currently blocked waiting for a slot to become available. This means the runner has jobs it wants to run but there are no idle slots to assign them to. A sustained non-zero pending count indicates the autoscaler needs to provision more instances.
* Acquired — Slots that have an active task running on them. This is the count of slots currently in use executing a job. In theory, `fleeting_taskscaler_tasks{state="acquired"}` should roughly correspond to `gitlab_runner_jobs{state="running"}`.
* Reserved — Slots that have been claimed by an `Acquire()` call but whose task hasn't started or completed yet. This is the transitional state between a slot being handed out to the runner and the job actually running on it.
* Unavailable — Slots on instances that have reached their max_use_count of 1 but still have an in-progress task. These slots will never accept a new task; the instance is being drained and will be deleted once its remaining work finishes.
* Unhealthy — Slots on instances that have been marked unhealthy (e.g. connectivity issues). These slots exist but cannot be assigned tasks until the instance recovers or is replaced.

### Fleeting Instance creation timing vs Fleeting instance is_running timing

It is easy to mistakenly believe these `Fleeting Instance creation timing` vs `Fleeting instance is_running timing` graphs are identical. However, they are generated from `fleeting_provisioner_instance_creation_time_seconds_bucket` and `fleeting_provisioner_instance_is_running_time_seconds_bucket` metrics respectively and these metrics are very, very subtley different.

Both metrics measure the same duration between when the instance is requested and when it is provisioned. The only difference is when each metric is recorded.

`fleeting_provisioner_instance_creation_time_seconds_bucket` is recorded immediately when the instance first appears.
`fleeting_provisioner_instance_is_running_time_seconds_bucket` is recorded only when the instance reaches `StateRunning`.

This means the only time these metrics will differ significantly is

* when an instance is first discovered in a non-running state, and then only some time later (late enough to be moved into a different bucket) it is transferred to a running state AND/OR
* an instance is never transitioning to a running state at all if they are deleted or timed out while still creating.

### Gitlab API request_job duration

This graph measures the runner stack's impression of how long a request to `/api/v4/jobs/request` endpoint is taking to return.

You should compare the p50, p90 and p99 durations for a specific runner stack in `Gitlab API request_job duration` graph to the `duration_s`,`db_duration_s`,`queue_duration_s`,`gitaly_duration_s`,`redis_duration_s`,`view_duration_s` values in Opensearch where `path: /api/v4/jobs/request` to see if the Runner Stack and Rails agree about the duration of requests to that `request_job` endpoint.

If they both agree that `request_job` endpoint is slow, investigate [Non-DHR causes of DHR Slow Performance](#non-dhr-causes-of-dhr-slow-performance).

If they significantly diverge, investigate the possibility of slow network between DHR and the Tenant, or saturation on the Runner Manager instance itself.

## Emergency Doubling of DHR Capacity

[Zero Downtime Deployments in DHR](https://gitlab-com.gitlab.io/gl-infra/gitlab-dedicated/team/architecture/blueprints/hosted-runner-zero-downtime.html#zero-downtime-implementation-for-hosted-runners) mean that we usually have 1 active shard and 1 inactive shard for every DHR Runner Stack.
In an emergency it is possible to double capacity of a DHR stack by [running `hosted_runner_provision` without also running `hosted_runner_shutdown` and `hosted_runner_cleanup`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#:~:text=Tasks%60%20%2D%3E%20select%20%60hosted_runner_deploy%60-,b.%20Jobs%20Method,-i.%20In%20Switchboard). This brings up the second shard for that stack, but does not shut down the first - leaving DHR in a state where there are two healthy shards able to process jobs.

Realize that doing this is deliberately recreating an [inaccuracy between deployment_status SSM Parameter and state of infrastructure](./inaccuracies-between-deployment_status-ssm-parameter-and-state-of-infrastructure.md). Specifically, you are creating a situation where a shard is healthy, but is NOT marked as `active_shard`, and is in `deployed_shards`.

This will need to be reverted by running `hosted_runner_shutdown` and `hosted_runner_cleanup` before the next time someone runs `hosted_runner_provision` - aka before the next maintainence window or emergency deployment.

## Non-DHR causes of DHR Slow Performance

As of the time of writing this runbook, we are yet to see conclusive evidence that a non-DHR component of Dedicated Architecture is causing slowness on DHR. However, we know it is theorically likely to occur at some point as it is one of the most common causes of Performance Problems on Gitlab.com Hosted Runners.

If you have exhausted your investigation of DHR components during a DHR performance problem it could be reasonable to consider slowness might be coming from one or more of the following:

* PostgreSQL Database
* Workhorse
* Sidekiq & Registry Kubernetes Cluster
* Gitaly

More understanding on these matters can be gathered by reading the Performance Troubleshooting Guidance for CI-Runners on Gitlab.com

* [Gitlab.com: Runner Manager's queues violating the SLI of the ci-runners service](../ci-runners/alerts/ci-apdex-violating-slo.md)
* [Gitlab.com: Large CI pending builds](../ci-runners/alerts/ci_pending_builds.md)

## Further Reading

1. [Advanced Configuration](https://docs.gitlab.com/runner/configuration/advanced-configuration/)Settings for Gitlab-Runner Binary
1. [How Jobs are picked up by the Runners](https://docs.gitlab.com/runner/configuration/advanced-configuration/)
1. Performance Troubleshooting Guidance for CI-Runners on Gitlab.com
a. [Gitlab.com: Runner Manager's queues violating the SLI of the ci-runners service](../ci-runners/alerts/ci-apdex-violating-slo.md)
b. [Gitlab.com: Large CI pending builds](../ci-runners/alerts/ci_pending_builds.md)

## Escalation Pathways

If you are in need of urgent help in a DHR incident with a Performance component, you can use `/incident escalate` in an incident slack channel, and then escalate to `tier2 - Runners Platform`.
