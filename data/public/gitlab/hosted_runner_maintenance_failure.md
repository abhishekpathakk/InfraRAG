# Hosted Runner maintenance for {customer} has failed

## General Troubleshooting DHR Maintenance Failure

First, know that it is very likely that only the inactive shard of the Dedicated Hosted Runner (DHR) is experiencing a problem, while the active shard is likely continuing to process jobs. You can verify this via looking at the [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards) and make sure that the active shard is still actually processing jobs.

Most of what you need to know about troubleshooting a failed hosted runner maintenance can be found under [Troubleshooting problems with ZDD in hosted-runners-troubleshooting.md in the team repo](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#troubleshooting-problems-with-zdd).

## Specific known categories of DHR Maintenance Failure

1. [Hosted_runner_provision post deploy healthcheck failed](./provision_post_deploy_healthcheck_failed.md)
1. [Hosted_runner_provision pre deploy healthcheck failed](./provision_pre_deploy_healthcheck_failed.md)
1. [Inaccuracies between deployment_status SSM Parameter and state of infrastructure](./inaccuracies-between-deployment_status-ssm-parameter-and-state-of-infrastructure.md)
1. [`hosted_runner_prepare` has failed with `Error: Error acquiring the state lock`](./prepare_error_state_lock.md)

### Once `hosted_runner_provision` succeeds

After you rerun `provision` successfully, please also always run `shutdown` and `cleanup` so that we don't waste money and cause confusion by having both colours live at the same time.

If you had to do some serious shenanigans to get a successful run of `hosted_runner_provision`, it is **highly recommended** that you rerun the entire `hosted_runner_deploy` pipeline for that runner stack and getting a clean successful maintenance before moving on. This is especially relevant if you had to fix an infrastructure issue on one shard, as the same problem may be present on the other shard.
