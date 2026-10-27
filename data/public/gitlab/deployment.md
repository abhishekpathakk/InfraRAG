# macOS runner fleet deployments

Generally, we follow the standard runner [blue/green deployment process](../linux/blue-green-deployment.md).

However, given the nature of [dedicated hosts](./dedicated_hosts.md) and potential capacity issues we try to do so in periods of lower utilization, such as weekends.
Peak utilization seems to be EMEA weekdays.

View the current job and historic utlization on the [CI runners dashboard](https://dashboards.gitlab.net/d/ci-runners-deployment/ci-runners3a-deployment-overview?orgId=1&from=now-12h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-type=ci-runners&var-shard=saas-macos-medium-m1&var-shard=saas-macos-large-m2pro&var-runner_job_failure_reason=$__all&var-project_jobs_running=$__all).

Further, given we maintain a number of components for macOS (host image, job images, nesting etc), it is sensible to test any changes in our staging shard `saas-macos-staging` first. Once this is deployed to, test pipelines can be run [in the saas-macos-staging test project](https://gitlab.com/gitlab-org/ci-cd/tests/saas-runners-tests/macos-platform/saas-macos-staging-basic-test/-/pipelines).

Due to the number of steps involved in macOS we follow the [change request workflow process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/#change-request-workflows).
See [an example macOS CR](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22321) that updates both the runner and job/host images.
When creating a new CR, use [GitLab Duo](https://docs.gitlab.com/ee/user/gitlab_duo/) to create a copy of an existing one, providing all the details of what is changing, including the deployment colors.
This is a lot quicker than creating it manually, but still be sure to read it through before having it reviewed.

## Pre-flight checks

All shards are configured to hold onto dedicated hosts rather than release them when the running instance is terminated.
This is because, in the US regions at least, it is [increasingly difficult to acquire macOS dedicated hosts](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28349) dynamically.

Before switching deployments ensure that enough dedicated hosts exist to scale into and meet current demand.
You can view the number of jobs running currently through [this ci-runners Grafana panel](https://dashboards.gitlab.net/d/ci-runners-deployment/ci-runners3a-deployment-overview?orgId=1&from=now-1h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-type=ci-runners&var-shard=saas-macos-medium-m1&var-shard=saas-macos-large-m2pro&var-runner_job_failure_reason=$__all&var-project_jobs_running=$__all&viewPanel=panel-8).
Generally `number of running jobs / 2 = required number of hosts` due to each host being able to run 2 VMs concurrently.
We do not expose this data to our central metrics stack ([yet](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/work_items/4337)),
so you must log into each AWS account and check the dedicated hosts list (under EC2), or use the aws cli, e.g.:

```sh
aws ec2 describe-hosts --region "us-east-1" --filter "Name=state,Values=available" --query "Hosts[?length(Instances) == \`0\`].[HostId,HostProperties.InstanceType,AvailabilityZone,State]" --output table
```

Once the older shard is shut down it can take 3-4 hours before freed dedicated hosts become available again for use.
See [dedicated hosts overview](./dedicated_hosts.md) for more details.

## `mac2.metal` flakiness

Environments using `mac2.metal` hosts (`saas-macos-staging` and `saas-macos-medium-m1`) often experience
instance instability problems.

These problems manifest in two ways:

- Instance SSH startup failures - access fails after about 5 minutes, but before being fully provisioned.
- Dedicated hosts become unhealthy according to AWS checks and are recycled.

The runner handles these issues correctly by terminating the instance.
This does have the negative side effect of using utilising more dedicated hosts
than would otherwise be optimal.

We don't know why these things occur specifically on the `mac2.metal` hosts.
The same problems are not observed on `mac2-m2pro.metal` machines,
which are both newer and have more resources.

`mac2.metal` is the oldest generation of arm64 mac minis in AWS. It is likely that this
hardware is coming to the end of its lifetime.
