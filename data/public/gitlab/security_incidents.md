## Responding to SIRT Incidents on Dedicated Hosted Runners (DHR)

It is very important in a security incident to follow the [Security Incident Response Guide](https://handbook.gitlab.com/handbook/security/security-operations/sirt/sec-incident-response/) and prioritize what is written there and the instructions of the SIRT team over any instructions in this runbook.

This runbook is just a collection of various skills it might be useful to employ during SIRT Incidents for DHR.

### Rotating Runner Tokens for DHR

> [!note]
> This is a Zero Downtime operation.

1. [Create a new Runner Token for a Runner Stack](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/recreate-runner-token-for-hosted-runner)
1. Use [Hosted Runners Overview dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards) and make sure that the new active shard is actually processing jobs.
1. Ask the Dedicated EOC to use [the Rails Console on Customers Dedicated GitLab Instance](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/connecting-to-aws-resources.md#rails-console) to revoke the old Runner Token, OR ask the customer to delete the old Runner Token.

### Rotating the `aws_iam_access_key` for the `fleeting_service_account` (`aws_iam_user` named after the Runner Shard)

> [!note]
> This is a Zero Downtime operation.

The `aws_iam_user` used by a runner shard will have the same name as the shard itself, e.g. `blue-abc123` will have an IAM user named `blue-abc123`.

1. Identify inactive shard using the [Grafana Dashboard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md?plain=0#dashboards)
1. [Breakglass into AMP pod for provision](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#bring-up-an-amp-operator-shell-on-a-dhr-account)
1. [Init Terraform state for inactive shard](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#correct-method-to-intialize-terraform-state-prior-to-manual-state-operations-via-amp)
1. Confirm access key for inactive shard `terraform state show module.grit_iam.aws_iam_access_key.fleeting_service_account_key`
1. Destroy the access key for inactive shard `terraform destroy -target=module.grit_iam.aws_iam_access_key.fleeting_service_account_key`
1. Run [`hosted_runner_deploy`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-tasks.md#immediately-applying-changes:~:text=a.%20Tasks%20Method%20(preferred%20in%20most%20cases)) to do a ZDD onto the inactive shard. Terraform will automatically recreate the access key
1. It is likely wise to do this on both shards of a given runner stack.

Ideally we will eventually move to using [IAM roles instead of static access keys](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/work_items/11879) and IAM users for fleeting, which will mean this skill is unnecessary.

### Identifying details about the job run on a specific ephemeral job machine using Opensearch

1. [Access the customer's Opensearch](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#accessing-logs-in-opensearch)
1. Run the query `fluentd_tag: "*-manager-logs" AND json.instance-id: "*{instance_id}*" AND json.project: "**"` substituting in your `instance_id`.
1. The log that returns should include

- `json.gitlab_user_id`
- `json.instance-id`
- `json.internal-address`
- `json.job`
- `json.namespace_id`
- `json.organization_id`
- `json.project`
- `json.project_full_path`
- `json.root_namespace_id`
- `json.runner`
- `json.runner_name`
- `json.time`

etc etc

### Manually blocking a specific IP on a hosted runner VPC via the AWS console

> [!note]
> This is a Zero Downtime operation and is easily reverted

1. [Breakglass](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/incident-management/-/blob/main/procedures/break-glass.md) into the customer's DHR AWS account.
1. Go to VPCs in AWS.
1. Go to Network ACLs
1. Find the Network ACL for the specific VPC
1. Click on the Outbound Rules tab
1. Edit Outbound Rules
1. Add a new rule with a lower Rule Number than any existing rule
1. Set Type: All traffic
1. Set Destination: the specific IP/Port of the IP to be blocked in CIDR notation (e.g. `127.0.0.1/32`)
1. Set Allow/Deny = Deny
1. Save

It is very important to follow the breakglass procedure and record what was done to the Network ACLs for follow up and ideally codification.

Ideally we will eventually move to using [AWS Firewall Rules](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/work_items/11881) which have the ability to block entire domains instead of just IP addresses.


### Manually deleting a specific IAM Role from a DHR Account

[Delete an IAM Role via AMP Pod](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/blob/main/runbooks/hosted-runners-troubleshooting.md#delete-an-iam-role-via-amp-pod)
