# Cell Provisioning and De-Provisioning

## Prerequisites

- Configure [`ringctl` in your environment](https://gitlab.com/gitlab-com/gl-infra/ringctl#preparing-your-environment).
- Confirm that you have access to the [`cells/tissue`] project
- Clone the [`cells/tissue`] project locally

## How to Provision a new Cell

[`ringctl`](https://gitlab.com/gitlab-com/gl-infra/ringctl) uses adaptive deployment strategy, i.e it takes reference from the existing tenant_model from a target_ring and replaces only the necessary fields. The cloud provider where a cell should be provisioned must also be provided.

> [!note]
> For most cases you would want to take reference from the `ring 0`.

### Provisioning Steps

#### 1. Create a new tenant using a cell from the target ring as reference

A cell from the given Amp environment, ring, and the requested cloud provider will be used as a reference. A tenant model will be created for a new cell, and it will have the given cell ID. (Cell ID needs to be registered with the topology service, so the user must specify it here.)

```bash
ringctl cell provision --dry-run --amp_environment <cellsdev|cellsprod> --ring 0 --cloud_provider <aws|gcp> --cell_id <cell_id>
```

> [!note]
> When provisioning an AWS cell, this step must always be performed with a local copy of tissue using the flags `--local --chdir /path/to/local/cells/tissue`. This is because we need to manually create an AWS account and replace the placeholder value of the AWS account ID with the new AWS account ID before proceeding to the further steps in this guide.

<details>
<summary>Example Run</summary>

**Command:**

```bash
ringctl cell provision --dry-run --local -C ../cells/tissue --cloud_provider aws --ring 0 --cell_id 200
```

**Output:**

```bash
$ ringctl cell provision --dry-run --local -C ../cells/tissue --cloud_provider aws --ring 0 --cell_id 200
time=2025-08-28T10:07:15.568+09:00 level=WARN msg="DELIVERY_METRICS_URL or DELIVERY_METRICS_TOKEN not set, disabling metrics" DELIVERY_METRICS_URL=""
time=2025-08-28T10:07:15.568+09:00 level=INFO msg="tissue client initialized" instance=https://ops.gitlab.net branch=main dry_run=true amp=cellsdev project=gitlab-com/gl-infra/cells/tissue version=dev-gunknow-dirty local=true
time=2025-08-28T10:07:15.568+09:00 level=INFO msg="adding new tenant" ring=0 amp=cellsdev
time=2025-08-28T10:07:15.568+09:00 level=INFO msg="fetching cells list from ring" ring=0
time=2025-08-28T10:07:15.568+09:00 level=WARN msg="AWS tenant generation requires a manual step. Create an AWS account for this tenant and replace the placeholder_aws_account_id with the generated account ID. Follow this manual process: https://gitlab.com/gitlab-com/gl-infra/tenant-scale/cells-infrastructure/team/-/issues/438#note_2674468049. See https://gitlab.com/gitlab-com/gl-infra/delivery/-/issues/21311 for future plans." new_tenant_id=c01k3q3dwzgeajqxb2 placeholder_aws_account_id=PLACEHOLDER-AWS-ACCOUNT-ID
time=2025-08-28T10:07:15.568+09:00 level=INFO msg="new tenant generated" tenant_id=c01k3q3dwzgeajqxb2 reference_tenant_id=c01k21yz9qqajjfn6z

$ cat ../cells/tissue/rings/cellsdev/-1/c01k3q3dwzgeajqxb2.json
{
  "$schema": "https://gitlab-com.gitlab.io/gl-infra/gitlab-dedicated/tenant-model-schema/v1.80.0/tenant-model.json",
  "amp_aws_account_id": "537566696576",
  "amp_node_role_arns": [
    "arn:aws:iam::537566696576:role/restoretest_irsa_role",
    "arn:aws:iam::537566696576:role/prepare_irsa_role",
    "arn:aws:iam::537566696576:role/onboard_irsa_role",
    "arn:aws:iam::537566696576:role/provision_irsa_role",
    "arn:aws:iam::537566696576:role/configure_irsa_role",
    "arn:aws:iam::537566696576:role/qa_irsa_role"
  ],
  "audit_logging": false,
  "aws_account_id": "PLACEHOLDER-AWS-ACCOUNT-ID",
  "backup_region": "eu-west-1",
  "byod": {
    "instance": "staging.gitlab.com"
  },
  "cells": {
    "cell_id": 200,
    "database": {
      "skip_sequence_alteration": false
    },
    "topology_service_client": {
      "address": "topology-grpc.staging.runway.gitlab.net:443"
    }
  },
  "clickhouse": {
    "enabled": false
  },
  "cloud_provider": "aws",
  "cloudflare_waf": {
    "enabled": true,
    "migration_stage": "COMPLETE",
    "proxied": "PROXIED_RESTRICTED"
  },
  "external_smtp_parameters": {
    "authentication": "login",
    "domain": "mg.staging.gitlab.com",
    "from": "gitlab@mg.gitlab.com",
    "host": "smtp.mailgun.org",
    "pool": true,
    "port": 2525,
    "reply": "noreply@staging.gitlab.com",
    "starttls": true,
    "tls": false,
    "username": "postmaster@mg.staging.gitlab.com"
  },
  "gitlab_custom_helm_chart": {
    "version": "9.1.2-390132"
  },
  "gitlab_inter_pod_tls_enabled": true,
  "gitlab_version": "17.10.7",
  "instrumentor_version": "v17.132.0",
  "internal_reference": "cell-c01k3q3dwzgeajqxb2",
  "managed_domain": "cell-c01k3q3dwzgeajqxb2.gitlab-cells.dev",
  "onboarding_state_region": "us-east-1",
  "perform_qa": true,
  "prerelease_version": "18.4.202508260236-29ee9d9c17d.787b1324c36",
  "primary_region": "us-east-1",
  "reference_architecture": "ra3k_v3",
  "reference_architecture_overlays": [],
  "root_ca": {
    "aws_account_id": "245991315407",
    "region": "us-east-1"
  },
  "sandbox_account": false,
  "site_regions": [
    "us-east-1"
  ],
  "tenant_id": "c01k3q3dwzgeajqxb2",
  "use_gar_for_prerelease_image": true
}
```

</details>

#### 2. [For AWS cells only] Create AWS account

> [!warning]
> This is a required manual step when creating AWS cells. Unlike GCP, where the project ID can be pre-populated, an AWS account ID only exists after the account has been created. So, the account must be generated before the tenant model can be finalized.

The AWS account is created by running the Instrumentor `account-create-aws` script from inside an `accountcreate` operator-access job pod on the target Amp cluster.

1. Note the `tenant_id` generated in the previous step. This is the `tenant_id` field of the new tenant model, which is also the file name.

2. From a local checkout of the [`amp`] project, authenticate to the Amp cluster and start an `accountcreate` operator-access job pod:

   ```bash
   ./scripts/amp-operator-access.sh -s accountcreate -e <cellsdev|cellsprod>
   ```

   This drops you into a shell inside the job pod, which runs the Instrumentor image.

   > [!note]
   > A schema validation warning (`schema validation directory does not exist` / `unable to resolve tenant`) is printed when the shell starts. This is expected for this manual workflow and can be ignored. You still get an interactive shell in the pod.

3. Inside the pod, export the tenant ID and environment:

   ```bash
   export TENANT_ID=<tenant_id>
   export ENVIRONMENT=<cellsdev|cellsprod>
   ```

4. Run the account creation script:

   ```bash
   ./bin/account-create-aws
   ```

   The script assumes the `accountcreator_<environment>` role in the environment's management account, creates the AWS account (named after the `tenant_id`), waits for it to become available, and moves it into the `<Environment> Tenants` organizational unit. It is idempotent, so it is safe to re-run.

   > [!note]
   > When run manually like this, there is no `CALLBACK_ID`, so the script does not report the account ID back to Instrumentor. You must copy the account ID from the output yourself (next step).

5. Copy the new AWS account ID from the output. It is printed near the end in the callback message:

   ```
   + message='{
     "aws_account_id": "373633008521"
   }'
   ```

Once the AWS account is created, replace the string `PLACEHOLDER-AWS-ACCOUNT-ID` with the generated AWS account ID in the local tenant model file.

For historical context on the original bring-up of this process, see the [issue thread](https://gitlab.com/gitlab-com/gl-infra/tenant-scale/cells-infrastructure/team/-/issues/438).

#### 3. Create a Merge Request in [`cells/tissue`]

The tenant model for the new cell will be created in your local copy of [`cells/tissue`] at `rings/${amp_environment}/-1/${tenant_id}.json`. The cell *must* always be placed in the quarantine ring -1 at this stage. Create a feature branch from the latest default branch, commit this file, and create a merge request in the [`cells/tissue`] project. The canonical code for `cells/tissue` is on the `https://ops.gitlab.net` GitLab instance.

#### 4. Register the new cell in the [`topology-service-deployer`] config

> [!warning]
> This step *must* be completed, and the change deployed, before the [Instrumentor stages] are triggered. The `configure` stage alters the database sequence range for the cell based on the topology service configuration. If the cell is not yet registered, the sequence range is never altered and the cell ends up with a range that overlaps with existing cells. This causes ID conflicts (for example, on organization ID `1`) and requires the cell to be de-provisioned and re-provisioned. See <https://gitlab.com/gitlab-com/gl-infra/tenant-scale/cells-infrastructure/team/-/work_items/941> for an example of this failure.

Create a merge request in the [topology-service-deployer](https://gitlab.com/gitlab-com/gl-infra/cells/topology-service-deployer/-/tree/main?ref_type=heads) project that adds the new cell to the `cells` list for the target environment (`jsonnet/production.libsonnet` for `cellsprod`, `jsonnet/staging.libsonnet` for `cellsdev`), then regenerate the `.runway/topology-grpc/env-*.yml` and `.runway/topology-rest/env-*.yml` files. For each new cell, set:

- `id`: the `cell_id` chosen in step 1.
- `address`: the `managed_domain` from the tenant model created in step 1.
- `session_prefix`: `cell-<cell_id>`.
- `sequence_ranges`: the next free, non-overlapping range following the existing cells in that environment.

Example entry, taken from <https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer/-/merge_requests/43>:

```jsonnet
{
  id: 3,
  address: "cell-c01k35wpsh58x0j74g.cells.gitlab.com",
  session_prefix: "cell-3",
  sequence_ranges: [
    {
      minval: 1100000000000,
      maxval: 1199999999999,
    },
  ],
},
```

Get the MR reviewed, merged, and confirm that the topology service deployment has completed before continuing.

#### 5. Trigger the [Instrumentor stages] for cell provisioning

Once an MR has been created, the deployment pipeline to trigger Instrumentor stages can be triggered using `ringctl`. The MR *does not* need to be merged at this stage.

```bash
ringctl cell deploy --amp_environment <cellsdev|cellsprod> <tenant_id> --only-gitlab-upgrade=false --branch <feature_branch_name>
```

When all the [Instrumentor stages] pass successfully, the MR that introduces the cell should be merged into the default branch.

> [!note]
> This command will output a link to the cell pipeline which you can use to track the deployment progress.
> The pipeline will run all the Instrumentor stages to create your cell.

> [!warning]
> **Only for AWS cells:**
>
> The `provision` stage might fail with an error like the following one:
>
> ```
> │ Error: waiting for EKS Node Group (c01k35wpsh58x0j74g:c01k35wpsh58x0j74g-sidekiq-2025082602513657160000002f) create: unexpected state 'CREATE_FAILED', wanted target 'ACTIVE'. last error: eks-c01k35wpsh58x0j74g-sidekiq-2025082602513657160000002f-5ecc7224-e293-64be-2957-521cd8136265: AsgInstanceLaunchFailures: Could not launch On-Demand Instances. VcpuLimitExceeded - You have requested more vCPU capacity than your current vCPU limit of 32 allows for the instance bucket that the specified instance type belongs to. Please visit http://aws.amazon.com/contact-us/ec2-request to request an adjustment to this limit. Launching the EC2 instance failed.
> ```
>
> A quota increase for the newly created AWS account is requested automatically by Instrumentor in accordance with the reference architecture that was chosen for the cell. This happens in the [`onboard` stage](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/instrumentor/-/blob/e36eae24c365b167b27063170fe990bb0b906cd6/aws/onboard/modules/onboard-regional/service-quotas.tf#L32). Quota increases are not instant on AWS: They can take up to 2 days to be approved and applied to an account. So, the `provision` stage should be retried _after_ the quota increase has been approved.

> [!warning]
> **Only for AWS cells:**
>
> The `prepare` stage might fail with an error where Amp is unable to assume the `dedicated/preparation` role within the newly created AWS account. This _might_ be because the [AWS StackSet] creation can take up to 24 hours. This is a known issue and the GitLab Dedicated team are tracking this in <https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/issues/9527>

> [!warning]
> **Only for GCP cells**
>
> The `prepare` stage might fail on the initial run with an error like:
>
> ```
> Error when reading or editing KMSKeyRing "projects/cell-c01jp4m0711mwrhb8j/locations/us-east1/keyRings/gld-single-region": googleapi: Error 403: Google Cloud KMS API has not been used in project 9065488916 before or it is disabled. Enable it by visiting <https://console.developers.google.com/apis/api/cloudkms.googleapis.com/overview?project=9065488916> then retry. If you enabled this API recently, wait a few minutes for the action to propagate to our systems and retry.
> ```
>
> This is expected as the cell project was just created and Google is still enabling the API. Retry the job after approximately 10 minutes to resolve this issue.

#### 6. Access the new cell

- Once the pipeline completes successfully, access your cell through the domain specified in the `managed_domain` field of the `TENANT_MODEL`
- **Example:** `https://cell-<tenant_id>.gitlab-cells.dev`

## How to Move Cells between Rings

Moving Cells between Rings is a logical operation that only impacts when the destination ring receives a new patch.
Cells in Quarentine (-1) Ring do not recieve any automation.
All other Rings will receive operations in order.

### Moving A Cell into Quarantine

1. Using `ringctl`:

    ```bash
    % ringctl cell quarantine <cell-id> --ring <ring-id> -b <branch-name>
    ```

    <details>
    <summary>Example Run</summary>

    ```bash
    % ringctl cell quarantine c01j2t2v563b55mswz --ring 0 -b jts/test
    time=2025-04-01T15:49:04.424-04:00 level=WARN msg="DELIVERY_METRICS_URL or DELIVERY_METRICS_TOKEN not set, disabling metrics" DELIVERY_METRICS_URL=""
    time=2025-04-01T15:49:04.424-04:00 level=WARN msg="using default text icons; please select your preferred set of icons and store the value in the ringctl.yml file"
    time=2025-04-01T15:49:04.530-04:00 level=INFO msg="tissue client initialized" instance=https://ops.gitlab.net branch=jts/test dry_run=false amp=cellsdev project=gitlab-com/gl-infra/cells/tissue version=dev-g92b52bf-dirty local=false
    time=2025-04-01T15:49:04.864-04:00 level=WARN msg="branch not found, searching in default branch" branch=jts/test default_branch=main
    New branch: jts/test
    You can open a merge request visiting
          https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/merge_requests/new?merge_request%5Bsource_branch%5D=jts%2Ftest
    time=2025-04-01T15:49:06.670-04:00 level=INFO msg="cell operation" ring=-1 amp=cellsdev action=move url=https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/commit/6ac6e3fca1b34cbc1022c966e4f7a2028bf5899e
    time=2025-04-01T15:49:06.671-04:00 level=INFO msg="Successfully quarantined cell" cell_id=c01j2t2v563b55mswz
    ```

    </details>

2. Open the Merge Request using the provided log output containing a link
3. Obtain review, approval, and merge the MR.

## How to Move a Cell Out of the Quarantine Ring

This is currently a manual process.

1. Interrogate the target cell configuration and the target Ring destination
2. Validate the version of Instrumentor is the same.
3. Validation the configuration of the cell is the same.
3. Validate the version of GitLab is installed, is the same.
5. If any of the above differ, [create a patch](./patching/creating.md) to address any concerns.
6. If the target cell is in a sane state, create an MR which moves the JSON file from the -1 directory to the target Ring directory
7. Obtain review, approval and merge the MR.

## How to De-Provision a Cell

1. **Ensure the target cell is in the quarantine ring:**
   - If not already there, create an MR to move the cell definition to the `-1` folder (quarantine ring)
   - Get the MR approved and merged

2. **Trigger the tear-down pipeline:**

   ```bash
   ringctl cell deprovision --cell <tenant_id> --ring -1 -e <cellsdev|cellsprod>
   ```

   > [!note]
   > This command will output a link to the cell pipeline which you can use to track the tear-down progress.

3. **Remove the cell definition:**
   - After the tear-down pipeline completes successfully, create an MR to delete the cell definition file from [`cells/tissue`](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/)
   - Get the MR approved and merged

[`cells/tissue`]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/
[`amp`]: https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp
[`topology-service-deployer`]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer
[Instrumentor stages]: https://gitlab-com.gitlab.io/gl-infra/gitlab-dedicated/team/engineering/Stages.html#stages
[AWS StackSet]: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacks.html
