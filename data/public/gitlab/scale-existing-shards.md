## Access requirements

- [ ]  [GPRD admin account access](https://handbook.gitlab.com/handbook/security/corporate/services/access-requests/#working-on-access-requests)
- [ ]  Chef server admin
- [ ]  Write access in repos:
  - [ ]  [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo)
  - [ ]  [config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt)
  - [ ]  [deployer](https://gitlab.com/gitlab-com/gl-infra/ci-runners/deployer)
  - [ ]  [infra-mgmt](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt)
  - [ ]  [runbooks](https://gitlab.com/gitlab-com/runbooks)

## About this document

This guide describes steps similar to those in the [new-shards.md](./new-shards.md) guide, however, scaling a shard requires a few less steps.

## Quota Increases

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/108)

1. Reach out to Google reps in `#ext-google-cloud` Slack channel.
   1. **NOTE:** Do this as early as possible in the process, as soon as we have an idea of many resources we’ll need, even before the projects exist. Do not assume we will have auto-approval on anything.
2. Collaborate with GCP reps on provisioning and due dates.
   1. [Planning sheet](https://docs.google.com/spreadsheets/d/11-pgtOZUS5FYkXxkY-KeN-MG5ySUoRSNM2LFsnTJJLg/edit?resourcekey=0-Sphm81BpjcG9rWqMh8y4rw#gid=633801891)
   2. [Planning doc](https://docs.google.com/document/d/1loZtcKB5XnuwS6MpnVw1qqZDwywlXpUqx6wQY0aB7G8/edit)
3. Submit standard quota increase requests in the GCP console.

:warning: If you need to increase quotas for `Heavy-weight read requests per minute`, it is possible you need to specifically increase `Heavy-weight read requests per minute per region` as seen in [this issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/16233).

Typically, the following quotas will need to be increased:

- N2D CPUs (us-east1)
- Read requests per minute per region (us-east1)
- Heavy-weight read requests per minute per region (us-east1)
- Queries per minute per region (us-east1)
- Concurrent regional operations per project per operation type (us-east1)

Compare the settings with other existing projects and request needed adjustments.

```
https://console.cloud.google.com/iam-admin/quotas?project=gitlab-r-saas-l-m-amd64-org-1&walkthrough_id=bigquery--bigquery_quota_request&pageState=(%22allQuotasTable%22:(%22f%22:%22%255B%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22N2D%2520CPUs_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22OR_5C_22_22_2C_22o_22_3Atrue%257D_2C%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22Heavy-weight%2520read%2520requests%2520per%2520minute%2520per%2520region_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22OR_5C_22_22_2C_22o_22_3Atrue%257D_2C%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22Read%2520requests%2520per%2520minute%2520per%2520region_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22OR_5C_22_22_2C_22o_22_3Atrue%257D_2C%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22Queries%2520per%2520minute%2520per%2520region_5C_22_22_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22OR_5C_22_22_2C_22o_22_3Atrue%257D_2C%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22In-use%2520IP%2520addresses_5C_22_22_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22OR_5C_22_22_2C_22o_22_3Atrue%257D_2C%257B_22k_22_3A_22Name_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22Concurrent%2520regional%2520operations%2520per%2520project%2520per%2520operation%2520type_5C_22_22_2C_22s_22_3Atrue_2C_22i_22_3A_22displayName_22%257D_2C%257B_22k_22_3A_22_22_2C_22t_22_3A10_2C_22v_22_3A_22_5C_22region_3Aus-east1_5C_22_22%257D%255D%22,%22s%22:%5B(%22i%22:%22displayName%22,%22s%22:%220%22),(%22i%22:%22currentPercent%22,%22s%22:%221%22),(%22i%22:%22sevenDayPeakPercent%22,%22s%22:%220%22),(%22i%22:%22currentUsage%22,%22s%22:%221%22),(%22i%22:%22sevenDayPeakUsage%22,%22s%22:%220%22),(%22i%22:%22serviceTitle%22,%22s%22:%220%22),(%22i%22:%22displayDimensions%22,%22s%22:%220%22)%5D))
```

## Document CIDRS

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/109)

1. Register unique CIDRs for the new ephemeral runner projects in the [Runbooks](../ci-runner-networking.md#ephemeral-runners-unique-cidrs-list)

## ****Define GCP projects in terraform****

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/110)

Create the projects for the ephemeral VMs in the [config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt) repo. Each runner manager will point to one of the projects created here.

1. Locate the shard you're scaling in [environments/env-projects/saas-runners.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/env-projects/saas-runners.tf)
2. Increase the `count` variable by the desired value.
3. Submit and merge an MR with your changes.
4. Confirm the projects are created successfully
   1. May require an SRE who has permissions to check, as most devs will not have permissions for these projects until the configuration step below when we grant permissions.

## ****Configure GCP projects in terraform****

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/111)

1. Locate the shard you're scaling under `ephemeral_project_networks` in [environments/ci/variables.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ci/variables.tf)
2. Add a new entry under `ephemeral_subnetworks` and `ephemeral_service_projects`.
5. Add the CIDRs under `ci-gateway-allow-runners` in [environments/gprd/main.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/main.tf) (using values set in the Document CIDRs step above)
6. Locate the directory for the shard name you're scaling under `environments/`
   1. Add a new entry for the new projects under the `project` variable in the `variables.tf` file.
7. At the root of `config-mgmt`, run `terraform fmt -recursive`
8. Submit an MR with your changes.

## ****Add chef-repo configs****

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/112)

Add the chef configs for the new runner-manager VMs. This will associate with `config.toml` settings on the runner managers, as well as some other settings (secrets config, analytics, etc).

1. Copy (and update as needed) the existing config for the `green` settings of one of the existing `runners-manager-<shard name>-green.json` under `roles/`.
2. Copy (and update as needed) the existing config for the `blue` settings of one of the existing `runners-manager-<shard name>-green.json` under `roles/`.

Note: initial `concurrent` setting should be `0` until we are ready to enable the runners

## ****Add secrets to vault****

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/114)

1. Locate the secrets vault for the shard you're scaling in [this location](https://vault.gitlab.net/ui/vault/secrets/chef/list/env/ci/cookbook/cookbook-gitlab-runner/).
2. Add two entries for each new runner-manager you're adding, one for the `green` and one for the `blue` secrets.

## Run chef-client on each new runner manager

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/115)

Note: will need chef server admin user and secrets in vault!

:warning: Ensure `concurrent` settings for any new runners is set to `0`.

SSH into each new runner-manager and initiate a `chef-client` run:

```bash
$ ssh runners-manager-private-green-9.c.gitlab-ci-155816.internal
$ sudo chef-client
```

## Set up TLS for each new runner manager

[reference issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/24011)

SSH into each new runner-manager and initiate a manual tls-certificate test:

NOTE: you'll need copy the `/tmp/create-machine.sh` and the `/tmp/test-machine.sh` from existing machines into the new VMs.

```bash
$ ssh runners-manager-private-green-9.c.gitlab-ci-155816.internal
$ export VM_MACHINE=docker-machine-tls-test-vm-01
$ /tmp/create-machine.sh && /tmp/test-machine.sh
```

If the run fails, you'll get an error hinting at the reason.

## Don't forget to remove any machines you manually created

`docker-machine rm -f $VM_MACHINE`

## Add projects to the reaper

The [reaper](https://gitlab.com/gitlab-com/gl-infra/reaper) deletes orphaned
ephemeral VMs. Its project list is in
`services/reaper/manifests/main.jsonnet` in `argocd/apps`: bump the family's
count, or add a family for a new project prefix. The reaper's service account
gets the `reaper` role in every project created through the
`ephemeral-vms-project` module in config-mgmt, so no IAM change is needed.


## Define cost factor

[reference issue](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/118)

## Raise concurrent levels

[reference issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/24144)

1. Update the `default_attributes.cookbook-gitlab-runner.global_config.concurrent` value to match max capacity in the json file for the entire shard in chef-repo.

## Enable the new runners on the existing shard

[reference issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/24134)

:warning: Ensure `concurrent` settings for the runners are production ready, usually set to `1200`.

SSH into each new runner-manager and run a `chef-client` as well as start/stop the `gitlab-runner` process depending on which runner is going to be active and which will be inactive. Suppose the `blue` deployment is inactive and the `green` is active, you'd perform the following:

```bash
$ ssh runners-manager-private-blue-9.c.gitlab-ci-155816.internal
$ sudo chef-client-disable "Disabling until next deployment"
$ sudo gitlab-runner stop

$ ssh runners-manager-private-green-9.c.gitlab-ci-155816.internal
$ sudo chef-client-enable
$ sudo chef-client
$ sudo gitlab-runner start
```

After ensuring the runner process is up, enable the new runner-manager VMs through a GitLab Admin account:

1. Login as an Admin.
2. Go to [the admin console](https://gitlab.com/admin/runners)
3. Filter using the shard's tag, for example:

    ![img.png](img.png)

4. Click the play button to enable each of the new machines.

    ![img_1.png](img_1.png)

## Unpause the new runners in GPRD

[reference issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/16104)

1. In the gitlab admin account, unpause the runners (only needs to be done once)
