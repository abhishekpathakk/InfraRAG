## Inaccuracies between deployment_status SSM Parameter and state of infrastructure

### Glossary

| Term | Meaning |
| ------ | --------- |
| SSM Parameter | `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` in Parameter Store in DHR AWS Account |
| `deployment_status` | `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` in Parameter Store in DHR AWS Account |
| healthy | shard is returning healthy on a `wait-healthy` deployer health check. Shard is _probably_ processing jobs for the customer. |
| active | shard is marked as `active_shard` in the SSM parameter `/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status` |

### Important Preliminary Understandings

The SSM Parameter `deployment_status` is an essential control for deciding which shard to provision, shutdown and cleanup during Zero Downtime Deployments.

The SSM Parameter `deployment_status` is updated as the last step in the `hosted_runner_provision` job. If any part of the provision job fails before the end, the SSM Parameter will not be updated and therefore may not accurately reflect the health of the shards.

We deliberately choose to only update the SSM Parameter as the very last step in a `hosted_runner_provision` job after a successful post-deploy health check. Given a choice between accidentally failing to mark a healthy shard as active_shard or deployed_shard, and accidentally marking an unhealthy shard or a never-deployed shard as `active_shard` or `deployed_shard`, we have a strong preference for the former.

Read [deployment_status SSM Parameter](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/ssm-parameter-for-dhr/runbooks/hosted-runners-troubleshooting.md?plain=0#deployment_status-ssm-parameter) for more.

### Initial Information Gathering

You can verify which shards are healthy via looking at the [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards) in Grafana. It is generally safe to assume that shards which are marked as Runner Manager Status Online OR are processing jobs will be returning healthy to a deployer `wait-healthy` check.

You can verify which shards are marked as active using `active_shard` in the [deployment_status ssm parameter](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#understanding-the-deployment_status-ssm-parameter)

You can verify which shards are marked as having been previously deployed using `deployed_shards` in the [deployment_status ssm parameter](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#understanding-the-deployment_status-ssm-parameter)

Post in the incident which shards are active, which have been previously deployed and which are healthy.

### Common Inaccuracies between `deployment_status` SSM Parameter and state of infrastructure

#### A shard is healthy and is marked as `active_shard`

This is the expected state of the active shard.

#### A shard is unhealthy, and is marked as `active_shard`

Follow the runbook for [Runners Manager is Down](./runners_manager_is_down.md)

#### A shard is unhealthy and is NOT marked as `active_shard`

This is the expected state of the inactive shard. It may or may not be in `deployed_shards`, depending on whether it has previously been deployed in the past. It may or may not have existing infrastructure in terraform, depending on whether or not `hosted_runner_cleanup` has finished running.

#### A shard is healthy, but is NOT marked as `active_shard`, and is in `deployed_shards`

This is the normal behaviour of a shard after a successful `hosted_runner_provision` job, but before the graceful_shutdown has completed in the `hosted_runner_shutdown` job. Either run `hosted_runner_shutdown` or wait for an existing hosted_runner_shutdown job to complete. Then run `hosted_runner_cleanup`.

Alternatively, this is also the behaviour that occurs if the `hosted_runner_provision` job failed on post-deploy healthcheck, but the shard is actually healthy. Follow the runbook for [Hosted_runner_provision post deploy healthcheck failed](./provision_post_deploy_healthcheck_failed.md) if you are struggling with `hosted_runner_provision` job failed on post-deploy healthcheck.

#### A shard is unhealthy and is NOT in `deployed_shards`

This is the expected state of a shard that has never been deployed in the past.

#### A shard is healthy, but is NOT in `deployed_shards`

If the `hosted_runner_provision` job fails during the very first deployment of a new shard:

- **but** the `hosted_runner_provision` job got far enough through the `hosted_runner_provision` job before failure that the shard is healthy,
- **and** then the second attempted execution of `hosted_runner_provision` on the same shard fails with "Inactive shard appears healthy, aborting to avoid unsafe deploy"
- **and** the shard is not in `deployed_shards`...

You may decide to manually edit the SSM parameter.

1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the DHR Production AWS Account.
1. Reconfirm the healthy, active and `deployed_shards` from [Initial Information Gathering](#initial-information-gathering). Post this information in the incident.
1. For example, if we're trying to deploy the runner for the first time to the blue shard, the SSM parameter will look like this: `{}` (an empty JSON object). Change it to `{"active_shard":"blue","deployment_ts":"2026-03-10T19:19:53Z","deployed_shards":["blue"]}` (with accurate timestamp). Run `hosted_runner_shutdown`, `hosted_runner_cleanup` (which will simply return `Runner RUNNER_NAME has 1 deployed shards — skipping shutdown` or `only one shard deployed, skipping` - but that's fine and accurate at this stage), then re-run the entire `hosted_runner_deploy` pipeline (which will create the green shard and swap to `"active_shard":"green"`).
1. For example, if we're trying to deploy to the green shard for the first time (and the blue shard has been deployed to previously), the SSM parameter will look like this `{"active_shard":"blue","deployment_ts":"2026-03-10T19:19:53Z","deployed_shards":["blue"]}`. Change to `{"active_shard":"blue","deployment_ts":"2026-03-10T19:19:53Z","deployed_shards":["blue", "green"]}` with accurate timestamp. Run `hosted_runner_shutdown`, `hosted_runner_cleanup` (which will shutdown the green shard) and then re-run the entire `hosted_runner_deploy` pipeline (which will recreate the green shard and swap to `"active_shard":"green"`).
