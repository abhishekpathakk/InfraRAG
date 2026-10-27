## hosted_runner_provision post deploy healthcheck failed

### Important Preliminary Understandings

First, know that it is very likely that only the inactive shard of the Dedicated Hosted Runner (DHR) is experiencing a problem, while the active shard is likely continuing to process jobs. You can verify this via looking at the [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards) and make sure that the active shard is still actually processing jobs.
As a general rule of thumb, it is safe to re-run hosted_runner_provision or other failed jobs in a hosted runner deployment.

Once `hosted_runner_provision` succeeds, follow the instructions under [Once hosted_runner_provision succeeds](./hosted_runner_maintenance_failure.md#once-hosted_runner_provision-succeeds) to make sure you leave the deployment tidy.

### Overview of troubleshooting paths

1. Open the job logs for the failed hosted_runner_provision job in Switchboard and read the error.
1. Rerun hosted_runner_provision. If that doesn't work -
1. Assuming that the Hosted Runner Provision post-deploy healthcheck failed, but no terrform errors are present in the logs - your first path is to trigger a [recreation of the relevant terraform resources](#recreating-the-relevant-terraform-resources).
1. If recreating the terraform resources and rerunning hosted_runner_provision does not cause the post deploy healthcheck to pass, your second path is to breakglass in and [troubleshoot why the gitlab-runner binary in the gitlab-runner container on the runner manager](#troubleshoot-why-the-gitlab-runner-binary-in-the-gitlab-runner-container-on-the-runner-manager-is-not-returning-healthy) is not returning healthy.

### Recreating the relevant terraform resources

There are multiple methods for recreating the relevant terraform resources. They are presented here ordered by easiest to hardest. If any one of these methods successfully recreates the relevant terraform resources as evidenced by the terraform logs in hosted_runner_provision, there is no need to try the other resource recreation methods.

NOTE: If you do not have specific reason to believe otherwise, it is usually ok to proceed with the assumption that the resource which is it most relevant to recreate is the `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`.

1. [Rerunning hosted_runner_provision](#rerunning-hosted_runner_provision)
1. [Running hosted_runner_cleanup, then rerunning hosted_runner_provision](#running-hosted_runner_cleanup-then-rerunning-hosted_runner_provision)
1. [Manually deleting the relevant terraform resources via the AWS console, then rerunning hosted_runner_provision](#manually-deleting-the-relevant-cloud-resources-via-the-aws-console-then-rerunning-hosted_runner_provision)
1. [Breaking glass into an amp pod, tainting the relevant terraform resources in the terraform state, then rerunning hosted_runner_provision](#breaking-glass-into-an-amp-pod-tainting-the-relevant-terraform-resources-in-the-terraform-state-then-rerunning-hosted_runner_provision)

#### Rerunning hosted_runner_provision

NOTE: This method will only create the resources that the terraform state does not already believe exist, and so you will not know whether the resources you are concerned with will be created without either a) trying it (good option, job can be rerun idempotently) or b) [breaking glass and checking the terraform state](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#correct-method-to-intialize-terraform-state-prior-to-manual-state-operations-via-amp) (bad option, unnecessary extra effort at this stage)

1. Check the job logs for the failed hosted_runner_provision job in Switchboard.
1. If the last attempt at hosted_runner_provision job logged `Apply complete! Resources: 0 added, 0 changed, 0 destroyed.`, and you have not taken any other action since that last job - then do not bother re-running hosted_runner_provision, as terraform will make no changes. Select a different method to recreate resources instead. Otherwise -
1. Rerun hosted_runner_provision
1. Check the job logs to see if it created relevant resources

#### Running hosted_runner_cleanup, then rerunning hosted_runner_provision

NOTE: This method will recreate all the terraform resources for the inactive shard in the provision stage.

NOTE: We never run hosted_runner_cleanup without first running hosted_runner_shutdown UNLESS we know that the inactive runner is in an unhealthy state, as evidenced by multiple post deploy healthcheck failures in hosted_runner_provision on the same inactive shard.

1. Check the job logs for the last two failed hosted_runner_provision jobs in Switchboard. Note that in both cases Transistor was attempting to deploy to the same inactive shard, which failed its post-deploy healthcheck both times. The fact that the hosted_runner_provision continues to attempt to deploy to the same shard proves that shard is the one marked as inactive in the ssm parameter, and the fact that the post-deploy health check continues to fail proves that the inactive shard is in an unhealthy state.
1. Run the hosted_runner_cleanup job. This will target that same inactive shard and delete that shards terraform resources. The job should log something like `Destroy complete! Resources: 13 destroyed.`
1. Rerun the hosted_runner_provision job. The job should log something like `Apply complete! Resources: 13 added, 0 changed, 0 destroyed.`

#### Manually deleting the relevant cloud resources via the AWS console, then rerunning hosted_runner_provision

NOTE: This method requires breakglass access into the DHR Production AWS Account

NOTE: This method as written will only recreate `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`, however you may adapt it by deleting other resources in the inactive shard in the provision stage as well if required.

1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the DHR Production AWS Account.
1. [Get very clear about which runner stack and shard is going to be deleted](#clarifying-which-runner-stack-and-shard-to-be-editted), and declare it in the incident.
1. Announce your intention in the incident to delete `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`.
1. Navigate to EC2 Instances in AWS, click on `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager` and use Instance State > Terminate (delete) instance to delete `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`
1. Rerun hosted_runner_provision, which should recreate `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`.

#### Breaking glass into an amp pod, tainting the relevant terraform resources in the terraform state, then rerunning hosted_runner_provision

NOTE: This method requires breakglass access into the Hub Production AWS Account

NOTE: This method as written will only recreate `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`, however you may adapt it by tainting other resources in the inactive shards terraform state in the provision stage as well if required.

1. [Get very clear about which runner stack and shard is going to be tainted](#clarifying-which-runner-stack-and-shard-to-be-editted), and declare it in the incident.
1. [Intialize terraform state prior to manual state operations via amp](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#correct-method-to-intialize-terraform-state-prior-to-manual-state-operations-via-amp)
1. Run `terraform state show "module.runner_manager.module.ec2[0].aws_instance.runner_manager"` and confirm that is the resource you want to taint
1. Run `terraform taint "module.runner_manager.module.ec2[0].aws_instance.runner_manager"`
1. Rerun hosted_runner_provision, which should recreate `{INACTIVE_SHARD}-{RUNNER_NAME}_runner-manager`.

### Troubleshoot why the gitlab-runner binary in the gitlab-runner container on the runner manager is not returning healthy

1. [Get very clear about which runner stack and shard is going to be investigated](#clarifying-which-runner-stack-and-shard-to-be-editted), and declare it in the incident.
1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the DHR Production AWS Account.
1. [Troubleshoot the gitlab-runner binary in the gitlab-runner container on the runner manager](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#valuable-troubleshooting-commands-to-run-for-a-gitlab-runner-inside-a-container-on-a-runner-manager)

#### If you decide to manually start the gitlab-runner binary on the inactive shard

If you manually start the gitlab-runner binary on the inactive shard, these things will happen

1. The inactive shard will immediately begin to process jobs for the customer. Since the active shard is still processing jobs as well, now both shards are processing customer jobs.
1. If you delete the runner manager or stop the gitlab-runner binary on the inactive shard after successfully starting it, this may be experienced by the customer as downtime, failed jobs, errors etc.

Consider these risks carefully and make sure other less potentially disruptive options have been exhausted or are not feasible before manually starting the gitlab-runner binary in the inactive shard.

##### If you attempt to manually start the gitlab-runner binary on the inactive shard and it fails

1. Continue troubleshooting

##### If you attempt to manually start the gitlab-runner binary on the inactive shard and it succeeds

If you attempt to manually start the gitlab-runner binary on the inactive shard and it succeeds, you still need to achieve a clean deployment of hosted_runner_provision and mark the newly healthy shard as active. For ease of understanding, pretend the inactive shard you have been troubleshooting is the pink shard, and the active shard which has been processing jobs this whole time is the purple shard.

1. Use [Grafana](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#dashboards) to confirm that the pink shard is now picking up jobs.
1. Edit the ssm parameter `"/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status"` to mark the pink shard as active, and the purple shard as inactive
1. Run hosted_runner_shutdown and hosted_runner_cleanup which will shutdown and cleanup the purple shard.

Now you are (theorically) in the state you would have been if the hosted runner maintenance never failed. The shards have flipped, and the pink shard is now active, and the purple shard is now inactive. However, you have not yet achieved a clean deployment of hosted_runner_provision. So to finalize, we suggest

1. Rerun the entire hosted_runner_deploy pipeline to get a clean execution of prepare, onboard, provision, shutdown and cleanup.

### Other Utility Steps

#### Clarifying which runner stack and shard to be editted

Before making any changes to infrastructure after breaking glass into a production environment, I recommend getting very clear about which runner stack and shard is going to be edited. This is assumed to be the inactive shard of the relevant runner stack.

1. State clearly in the incident which runner stack you are troubleshooting. There may be multiple runner stacks in a single DHR AWS account, and it is important to only change the correct runner stack.
1. Check the job logs for the last two failed hosted_runner_provision jobs for that runner stack in Switchboard. Confirm that in both cases Transistor was attempting to deploy to the same inactive shard, and it failed its post-deploy healthcheck both times. The fact that the hosted_runner_provision continues to attempt to deploy to the same shard proves that shard is the one marked as inactive in the ssm parameter, and the continuously failing post-deploy healthcheck proves that the shard is in an unhealthy state.
1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the DHR Production AWS Account.
1. Confirm using the ssm parameter `"/gitlab/dedicated/runner/{RUNNER_NAME}/deployment_status"` which shard is currently inactive. If the hosted_runner_provision job logs and the ssm parameter do not agree on which shard is inactive STOP HERE AND DO NOT PROCEED. You will need to use metrics to confirm which shard for that runner stack (if any) is currently processing jobs. Otherwise -
1. State clearly in the incident which runner shard you have confirmed is inactive
1. Proceed with planned changes.
