## `hosted_runner_provision` pre deploy healthcheck failed with `Inactive shard appears healthy, aborting to avoid unsafe deploy`

Quick Fix: Try jumping straight to [Graceful Shutdown and Redeploy](#graceful-shutdown-and-redeploy) and seeing if that resolves your problem. If not, return to the top of the runbook and work through systematically.

### Glossary

| Term | Meaning |
| ------ | --------- |
| SSM Parameter | `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` in Parameter Store in DHR AWS Account |
| `deployment_status` | `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` in Parameter Store in DHR AWS Account |
| healthy | shard is returning healthy on a `wait-healthy` deployer health check. Shard is _probably_ processing jobs for the customer. |
| active | shard is marked as `active_shard` in the SSM parameter `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` |

### Important Preliminary Understandings

If the `hosted_runner_provision` predeploy healthcheck is returning `Inactive shard appears healthy, aborting to avoid unsafe deploy` this means that a shard which is NOT marked `active_shard` in the `deployment_status` SSM parameter is returning healthy to a `wait-healthy` deployer check, and so `hosted_runner_provision` will fail. This is a very important safeguard in Zero Downtime Deployments to make sure we never deploy to a healthy shard which could be processing jobs.

Regardless of the status of the inactive shard of the Dedicated Hosted Runner (DHR), there may also be an active shard which is likely healthy and continuing to process jobs. You can verify this via looking at the [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards) and make sure that the active shard is still actually processing jobs.

Our goal is to get you into a state where:

- you only have 1 healthy shard processing jobs for the customer,
- that shard is marked active in the SSM Parameter, and
- you have had a successful clean run of `hosted_runner_deploy`.

However, we want to make sure we get to that state *without* causing customer facing errors or runner downtime. Ideally we want to gracefully shutdown the inactive shard (NOT suddenly delete or destroy it) then rerun the whole `hosted_runner_deploy` pipeline.

Once `hosted_runner_provision` succeeds, follow the instructions under [Once hosted_runner_provision succeeds](./hosted_runner_maintenance_failure.md#once-hosted_runner_provision-succeeds) to make sure you leave the deployment tidy.

### Initial information gathering

You can verify which shards are healthy via looking at the [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards). It is generally safe to assume that shards which are marked as Runner Manager Status Online OR are processing jobs will be returning healthy to a deployer `wait-healthy` check.

You can verify which shards are marked as active using `active_shard` in the [deployment_status ssm parameter](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#understanding-the-deployment_status-ssm-parameter)

You can verify which shards are marked as having been previously deployed using `deployed_shards` in the [deployment_status ssm parameter](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#understanding-the-deployment_status-ssm-parameter)

Post in the incident which shards are active, which have been previously deployed and which are healthy.

### Overview of troubleshooting paths

1. [Graceful Shutdown and Redeploy](#graceful-shutdown-and-redeploy)
1. [Forceful provision with --ignore-shard-healthcheck true](#forceful-provision-with---ignore-shard-health-true). Only try if Graceful Shutdown Path is unsuccessful, as may cause customer facing errors or runner downtime

### Graceful Shutdown and Redeploy

1. Run `hosted_runner_shutdown` and then `hosted_runner_cleanup` jobs in Switchboard to gracefully shutdown and then delete the resources for the inactive shard. The `hosted_runner_shutdown` and `hosted_runner_cleanup` jobs should accurately choose the inactive shard to shutdown and cleanup.
   - If `hosted_runner_shutdown` and/or `hosted_runner_cleanup` jobs fail, troubleshoot. Otherwise, proceed.
1. Read the logs to see if `hosted_runner_shutdown` and `hosted_runner_cleanup` actually performed a shutdown and cleanup. The logs should say `Shard has been {shutdown/cleaned up}`.
   - If `hosted_runner_shutdown` and `hosted_runner_cleanup` passed but returned `Runner RUNNER_NAME has 1 deployed shards — skipping shutdown` or `only one shard deployed, skipping`, **no graceful shutdown has actually occurred**. The inactive shard is still healthy. In that case, there is likely a mismatch between the actual health of the infrastructure and the state of the `deployment_status` SSM parameter. You should swap now to troubleshooting guide [Inaccuracies between deployment_status SSM Parameter and state of infrastructure](./inaccuracies-between-deployment_status-ssm-parameter-and-state-of-infrastructure.md) instead.
   - If the `hosted_runner_shutdown` and `hosted_runner_cleanup` actually performed a shutdown and cleanup, then you can now rerun `hosted_runner_deploy` pipeline and we would expect it to succeed.

#### Forceful provision with `--ignore-shard-health true`

> [!warning]
> If the inactive shard is healthy, it may be processing customer jobs. In that case, running `transistor provision --ignore-shard-health true` **may cause customer facing errors or runner downtime**. Only forcefully provision with `--ignore-shard-health` if you have exhausted all other options.

1. Read [Manually Running Provision, Onboard, Shutdown or Cleanup](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#manually-running-provision-onboard-shutdown-or-cleanup)
1. Read [Explaination of each flag in ZDD](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#explaination-of-each-flag-in-zdd) especially the sections [Potential Pitfalls of flag use](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#potential-pitfalls-of-flag-use) and [--ignore-shard-health Provision](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#provision). Only then proceed with awareness.

1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the DHR Production AWS Account.
1. [Bring up an amp operator shell on a DHR account](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#bring-up-an-amp-operator-shell-on-a-dhr-account) in the provision state.
1. Run `transistor provision --ignore-shard-health true`
1. Follow the instructions under [Once hosted_runner_provision succeeds](./hosted_runner_maintenance_failure.md#once-hosted_runner_provision-succeeds) to make sure you leave the deployment tidy.
