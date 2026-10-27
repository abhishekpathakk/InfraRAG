# Atlantis Setup Guide for Infrastructure Deployments

This guide outlines the steps to set up a dedicated Atlantis instance for managing Terraform deployments.
Assumes the project is running on ops.gitlab.net

## Prerequisites

- Access to GitLab infrastructure repositories
- Vault access for secret management
- Kubernetes cluster access for Atlantis deployment
- GCP project(s) for infrastructure resources
- Appropriate permissions for creating service accounts in Google project
- Access to [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt) repository for Atlantis service account setup
- Access to [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/config) repository for Atlantis workload configuration
- Access to [`infra-mgmt`](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt) repository for target project service accounts

> [!note]
> Make sure to update `INSTANCE-NAME` and `SERVICE-NAME` in the below examples to your target service, e.g. `topo-svc` and `ops-topo-svc`.

## Step 1: Configure Atlantis Workload and Secrets

> [!note]
>
> For a project on GitLab.com the instance name should be `com-SERVICE-NAME` (e.g. `com-runway-provisioner`).
>
> For a project on ops.gitlab.net the instance name should be `ops-SERVICE-NAME` (e.g. `ops-config-mgmt`).

### 1.1 Create Atlantis Instance

Create the `app.yaml` file for your Atlantis instance in the [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/master/services/atlantis/instances) repository:

**services/atlantis/instances/INSTANCE-NAME/app.yaml**:

```yaml
---
atlantis:
  enabled: true
  chart:
    # renovate: datasource=helm depName=atlantis registryUrl=https://runatlantis.github.io/helm-charts versioning=helm depType=prod
    version: 6.1.0  # set to current version of existing instances
```

### 1.2 Create Atlantis Instance Configuration

Create the Helm values file for your Atlantis instance:

**services/atlantis/instances/INSTANCE-NAME/values.yaml**:

```yaml
---
atlantisUrl: https://atlantis-INSTANCE-NAME.ops.gke.gitlab.net

apiSecretName: atlantis-api-INSTANCE-NAME
vcsSecretName: ops-gitlab-net-SERVICE-NAME
## For GitLab.com:
# vcsSecretName: gitlab-com-SERVICE-NAME

orgAllowlist: REPOSITORY-URL  # e.g. ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer

resources:
  requests:
    cpu: 4000m
    memory: 2Gi
  limits:
    cpu: 8000m
    memory: 4Gi

volumeClaim:
  dataStorage: 10Gi

serviceAccount:
  annotations:
    iam.gke.io/gcp-service-account: atlantis-INSTANCE-NAME@gitlab-ops.iam.gserviceaccount.com

podTemplate:
  labels:
    deployment: atlantis-INSTANCE-NAME

statefulSet:
  annotations:
    secret.reloader.stakater.com/reload: ops-gitlab-net-SERVICE-NAME,terraformrc
    ## For GitLab.com
    # secret.reloader.stakater.com/reload: gitlab-com-SERVICE-NAME,terraformrc
  labels:
    deployment: atlantis-INSTANCE-NAME
```

### 1.3 Configure Repository Workflow

Update [`services/atlantis/values-repo-config.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/atlantis/values-repo-config.yaml) to add the service repository configuration:

```yaml
repos:
  - id: REPOSITORY-URL  # e.g. ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer
    allowed_overrides: [delete_source_branch_on_merge]
    apply_requirements: [approved, mergeable]
    delete_source_branch_on_merge: true
    policy_check: true
    repo_locks:
      mode: on_apply
    workflow: SERVICE-NAME

workflows:
  SERVICE-NAME:
    plan:
      steps:
        - *env-terraform
        - *env-tf-comment-args
        - *env-tf-in-automation
        - *env-tf-input
        - *env-tf-plugin-cache-dir
        - &env-tf-var-vault-secrets-path-SERVICE-NAME
          env:
            name: TF_VAR_vault_secrets_path
            command: echo "PROJECT-PATH/${PROJECT_NAME}"  # e.g. gitlab-com/gl-infra/cells/topology-service-deployer/${PROJECT_NAME}
        - &env-tf-var-google-impersonated-account-SERVICE-NAME
          env:
            name: TF_VAR_google_impersonated_account
            value: atlantis-INSTANCE-NAME@gitlab-ops.iam.gserviceaccount.com
        - *env-vault-addr
        - *env-vault-auth-path
        - &env-vault-auth-role-SERVICE-NAME
          env:
            name: VAULT_AUTH_ROLE
            value: atlantis-ops-SERVICE-NAME
        - *env-vault-token
        - *cleanup-plugin-cache
        - *terraform-init
        - *terraform-plan
        - *tf-summarize
        - *terraform-show
        - *terraform-validate
    apply:
      steps:
        - *env-tf-in-automation
        - *env-tf-input
        - *env-tf-plugin-cache-dir
        - *env-tf-var-vault-secrets-path-SERVICE-NAME
        - *env-tf-var-google-impersonated-account-SERVICE-NAME
        - *env-vault-addr
        - *env-vault-auth-path
        - *env-vault-auth-role-SERVICE-NAME
        - *env-vault-token
        - apply:
            extra_args: ["-parallelism=20"]
```

### 1.4 Configure Ingress and Certificates

Update [Atlantis ingress configuration](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/1a6d350d8b75a3379c8a4e94e7cc3eb969c6ce94/services/atlantis/values.yaml#L48) to include your new Atlantis instance:

```yaml
ingress:
  ...
  hosts:
    - host: atlantis-INSTANCE-NAME.ops.gke.gitlab.net
      paths: ["/*"]
      service: atlantis-INSTANCE-NAME

# ...

extraManifests:
  - apiVersion: rbac.authorization.k8s.io/v1
    kind: ClusterRoleBinding
    metadata:
      name: '{{ include "atlantis.fullname" $ }}-auth-delegator'
    # ...
    subjects:
      # ...
      - kind: ServiceAccount
        name: atlantis-INSTANCE-NAME
        namespace: '{{ $.Release.Namespace }}'

  # ...

  - apiVersion: networking.gke.io/v1
    kind: ManagedCertificate
    metadata:
      name: atlantis-ops
    spec:
      domains:
        # ...
        - atlantis-INSTANCE-NAME.ops.gke.gitlab.net
```

### 1.5 Configure External Secrets

Create the External Secret Helm values file for your Atlantis instance:

**services/atlantis/instances/INSTANCE-NAME/values-vault-secrets.yaml**:

```yaml
externalSecrets:
  atlantis-api-INSTANCE-NAME:
    refreshInterval: 1h
    secretStoreName: atlantis-shared-secrets
    target:
      creationPolicy: Owner
      deletionPolicy: Delete
    data:
      - remoteRef:
          key: "atlantis/INSTANCE-NAME/api"
          property: secret
        secretKey: apisecret

  ops-gitlab-net-INSTANCE-NAME:
  ## For GitLab.com:
  # gitlab-com-INSTANCE-NAME:
    refreshInterval: 1h
    secretStoreName: atlantis-secrets
    target:
      creationPolicy: Owner
      deletionPolicy: Delete
    data:
      - remoteRef:
          key: "env/{{ .Values._clusterEnvironment }}/ns/atlantis/ops-gitlab-net"
          ## For GitLab.com
          # key: "env/{{ .Values._clusterEnvironment }}/ns/atlantis/gitlab-com"
          property: api_token
        secretKey: gitlab_token
      - remoteRef:
          key: "env/{{ .Values._clusterEnvironment }}/ns/atlantis/webhooks/INSTANCE-NAME"
          property: secret
        secretKey: gitlab_secret
```

### 1.6 Push changes to ArgoCD

Open a new MR with the above changes, then verify that all Atlantis applications are synced after merging it:

- <https://argocd.gitlab.net/applications/argocd/atlantis--a1ea8>
- `https://argocd.gitlab.net/applications/argocd/atlantis-instance--INSTANCE-NAME`

## Step 2: Create Atlantis Service Account and Permissions (via `config-mgmt`)

### 2.1 First MR: Configure Base Atlantis Service Account

Create the first merge request in the [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt) repository to set up the Atlantis service account.

**Create the Google Cloud service account with Kubernetes workload identity binding** in [`environments/ops/iam.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ops/iam.tf):

```hcl
module "atlantis-INSTANCE-NAME-sa" {
  source  = "terraform-google-modules/kubernetes-engine/google//modules/workload-identity"
  version = "37.0.0"

  project_id  = var.project
  name        = "atlantis-INSTANCE-NAME"
  namespace   = "atlantis"
  k8s_sa_name = "atlantis-INSTANCE-NAME"

  use_existing_k8s_sa = true
  annotate_k8s_sa     = false
}
```

### 2.2 Second MR: Configure Environment Project Permissions, Terraform state buckets, and Vault

**Once the first MR is merged and applied**, submit a second merge request to create the bucket with its permissions, plus storage, KMS, and Vault permissions.

**Register the service environments with Atlantis to enable Terraform state bucket creation** in [`atlantis.yaml`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/atlantis.yaml):

```yaml
projects:
  # ... existing projects ...

  # SERVICE-NAME
  - name: SERVICE-NAME-dev
    dir: environments/SERVICE-NAME-dev
    autoplan:
      enabled: false
  - name: SERVICE-NAME-prod
    dir: environments/SERVICE-NAME-prod
    autoplan:
      enabled: false
```

>[!note] This configuration file is used as a template for creating the required resources. [Example plan](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/11562#note_341200) the bucket
> is typically called "gitlab-infra-tf-[service-name]-[env]" it triggers changes in the `environments/env-environments` and `environments/vault-production`

**Grant the service account permissions to manage Terraform state files and encryption keys** in [`environments/env-projects/atlantis.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/env-projects/atlantis.tf):

```hcl
locals {
  atlantis_service_accounts = {
    # ... existing accounts ...
    [service-name] = {
      member       = "serviceAccount:atlantis-INSTANCE-NAME@gitlab-ops.iam.gserviceaccount.com"
      environments = toset(["SERVICE-NAME-dev", "SERVICE-NAME-prod"])
    }
  }
}

# Storage bucket permissions for Terraform state
resource "google_storage_bucket_iam_member" "terraform-state-object-admin-atlantis-SERVICE-NAME" {
  for_each = local.atlantis_service_accounts["SERVICE-NAME"].environments

  bucket = google_storage_bucket.infra-terraform[each.value].name
  role   = "roles/storage.objectAdmin"
  member = local.atlantis_service_accounts["SERVICE-NAME"].member

  depends_on = [module.gitlab-infra-terraform]
}

# KMS permissions for Terraform state encryption
resource "google_kms_crypto_key_iam_member" "terraform-state-encrypter-decrypter-atlantis-SERVICE-NAME" {
  for_each = local.atlantis_service_accounts["SERVICE-NAME"].environments

  crypto_key_id = google_kms_crypto_key.terraform-state-encryption[each.value].id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = local.atlantis_service_accounts["SERVICE-NAME"].member

  depends_on = [module.gitlab-infra-terraform]
}
```

**Configure Vault authentication and policies to give Atlantis access to read project secrets and write deployment outputs** in [`environments/vault-production/atlantis.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production/atlantis.tf):

```hcl
locals {
  # ... existing paths ...
  atlantis_ops_SERVICE-NAME_ro_paths = [
    "ci/GITLAB-INSTANCE/PROJECT-PATH/*",
    # e.g.
    # "ci/ops-gitlab-net/gitlab-com/gl-infra/cells/tissue/*",
  ]
  atlantis_ops_SERVICE-NAME_rw_paths = [
    "ci/GITLAB-INSTANCE/PROJECT-PATH/outputs/*",
    "ci/GITLAB-INSTANCE/PROJECT-PATH/+/outputs/*",
    # e.g.
    # "ci/ops-gitlab-net/gitlab-com/gl-infra/cells/tissue/outputs/*",
    # "ci/ops-gitlab-net/gitlab-com/gl-infra/cells/tissue/+/outputs/*",
  ]
}

# Kubernetes auth backend role
resource "vault_kubernetes_auth_backend_role" "atlantis-INSTANCE-NAME" {
  backend   = "kubernetes/ops-gitlab-gke"
  role_name = "atlantis-INSTANCE-NAME"

  bound_service_account_names      = ["atlantis-INSTANCE-NAME"]
  bound_service_account_namespaces = ["atlantis"]

  token_ttl     = 3600
  token_max_ttl = 7200

  token_policies = [
    vault_policy.atlantis-INSTANCE-NAME.name,
  ]

  depends_on = [module.vault-config]
}

# Vault policy document
data "vault_policy_document" "atlantis-INSTANCE-NAME" {
  # Child token creation by Terraform
  rule {
    path         = "auth/token/create"
    capabilities = ["update"]
  }

  # Allow to self lookup token
  rule {
    path         = "auth/token/lookup-self"
    capabilities = ["read"]
  }

  # Read-only access
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_ro_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/data/")
      capabilities = ["list", "read"]
    }
  }
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_ro_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/metadata/")
      capabilities = ["list", "read"]
    }
  }

  # Read-write access
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_rw_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/data/")
      capabilities = ["list", "read", "create", "patch", "update", "delete"]
    }
  }
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_rw_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/metadata/")
      capabilities = ["list", "read", "create", "patch", "update", "delete"]
    }
  }
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_rw_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/delete/")
      capabilities = ["update"]
    }
  }
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_rw_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/undelete/")
      capabilities = ["update"]
    }
  }
  dynamic "rule" {
    for_each = local.atlantis_ops_[service_name]_rw_paths
    content {
      path         = replace(rule.value, local.vault_kv_v2_expand_regex, "$1/destroy/")
      capabilities = ["update"]
    }
  }
}

# Vault policy
resource "vault_policy" "atlantis-INSTANCE-NAME" {
  name   = "atlantis-INSTANCE-NAME"
  policy = data.vault_policy_document.atlantis-INSTANCE-NAME.hcl
}
```

## Step 3: Configure Repository Access

- [Example secret MR](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt/-/merge_requests/2034)
- [Example webhook and user MR](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt/-/merge_requests/2018)

### 3.1 Add Atlantis User to Repository

Add the Atlantis user as a maintainer to your target repository in the [`infra-mgmt`](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt) repository:

```terraform
# In your GitLab project configuration
members = {
  (local.users.atlantis.id) = { access_level = "maintainer" }
}
```

### 3.2 Configure Webhook and secrets

Create a project webhook and generate secrets for Atlantis in the [`infra-mgmt`](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt) repository (assuming your project is on ops.gitlab.net):

```terraform

resource "random_password" "atlantis-INSTANCE-NAME-webhook-secret" {
  length  = 32
  special = false
}

ephemeral "random_password" "atlantis-INSTANCE-NAME-api-secret" {
  length  = 32
  special = false
}

# Secret for project to send events to Atlantis webhook
resource "vault_kv_secret_v2" "atlantis-INSTANCE-NAME-webhook" {
  mount = "k8s"
  name  = "env/ops/ns/atlantis/webhooks/INSTANCE-NAME"

  data_json = jsonencode({
    secret = random_password.atlantis-INSTANCE-NAME-webhook-secret.result
  })

  delete_all_versions = true
}

# Secret for making API requests to Atlantis server
resource "vault_kv_secret_v2" "atlantis-INSTANCE-NAME-api" {
  mount = "shared"
  name  = "data/atlantis/INSTANCE-NAME/api"

  data_json_wo = jsonencode({
    secret = ephemeral.random_password.atlantis-INSTANCE-NAME-api-secret.result
  })
  data_json_wo_version = 1

  delete_all_versions = true
}

resource "gitlab_project_hook" "SERVICE-NAME-atlantis" {
  project = module.project_canonical-SERVICE-NAME-deployer.id
  url     = "https://atlantis-INSTANCE-NAME.ops.gke.gitlab.net/events"
  token   = random_password.atlantis-INSTANCE-NAME-webhook-secret.result

  note_events           = true
  merge_requests_events = true
  push_events           = true

  enable_ssl_verification = true
}
```

## Step 4: Create Infrastructure Service Accounts

### 4.1 Create Target Project Service Accounts

First, create the service accounts that Atlantis will impersonate in your target GCP projects. These
need to have access to the resources that will be managed via terraform

[Example MR](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/merge_requests/470)

**Create service account configuration files:**

For **each** environment (`terraform/ENV/SERVICE-NAME-service-accounts.tf`):

```hcl
# Service accounts for the SERVICE-NAME
module "SERVICE-NAME_service_accounts" {
  source  = "ops.gitlab.net/gitlab-com/service-account/google"
  version = "1.0.0"
  for_each = {
    readwrite = [
      "roles/compute.admin",
      "roles/storage.admin",
      "roles/logging.admin",
      "roles/monitoring.admin"
    ]
    readonly = [
      "roles/compute.viewer",
      "roles/storage.objectViewer",
      "roles/iam.serviceAccountViewer",
      "roles/logging.viewer",
      "roles/monitoring.viewer"
    ]
  }

  project_id                          = "[Google project ID]"
  service_account_prefix              = "SERVICE-NAME"
  service_account_display_name_prefix = "SERVICE-NAME"
  suffix                              = each.key
  roles                               = each.value

  # Allow the Atlantis service account to impersonate these service accounts
  impersonation_members = [
    "serviceAccount:atlantis-INSTANCE-NAME@gitlab-ops.iam.gserviceaccount.com"
  ]
}

# Outputs
output "SERVICE-NAME_readwrite_service_account_email" {
  description = "The email of the SERVICE-NAME readwrite service account"
  value       = module.SERVICE-NAME_service_accounts["readwrite"].service_account_email
}

output "SERVICE-NAME_readonly_service_account_email" {
  description = "The email of the SERVICE-NAME readonly service account"
  value       = module.SERVICE-NAME_service_accounts["readonly"].service_account_email
}

```

## Step 5: Configure Target Repository

### 5.1 Add `atlantis.yaml` Configuration

Create `atlantis.yaml` in the repository root:

```yaml
---
version: 3
automerge: true
delete_source_branch_on_merge: true
parallel_plan: true
parallel_apply: true
abort_on_execution_order_fail: true

projects:
  - name: dev
    dir: terraform/dev
    execution_order_group: 1
  - name: prod
    dir: terraform/prod
    execution_order_group: 2
```

Configuration details can be found at <https://www.runatlantis.io/docs/repo-level-atlantis-yaml>

### 5.1 Add Terraform Configuration in the directory from previous step for each environment

Ensure your Terraform configuration includes:

```hcl
# Configure Terraform backend
terraform {
  backend "gcs" {
    bucket = "gitlab-infra-tf-SERVICE-NAME-ENV" # Created in step 2.2
    prefix = "SERVICE-NAME/PROJECT-NAME"
  }
}

## Google
provider "google" {
  credentials = var.google_application_credentials_path

  impersonate_service_account = var.google_application_credentials_path == null ? var.google_impersonated_account : null

  # Explicitly set the access_token to null to ensure we don't use
  # GOOGLE_OAUTH_ACCESS_TOKEN if it is in our environment
  # kics-scan ignore-line
  access_token = null
}

provider "google-beta" {
  credentials = var.google_application_credentials_path

  impersonate_service_account = var.google_application_credentials_path == null ? var.google_impersonated_account : null

  # Explicitly set the access_token to null to ensure we don't use
  # GOOGLE_OAUTH_ACCESS_TOKEN if it is in our environment
  # kics-scan ignore-line
  access_token = null
}


# Variables
variable "google_impersonated_account" {
  type        = string
  description = "Email of the service account to impersonate (mainly by Atlantis) if google_application_credentials_path is not set"
  default     = "atlantis-INSTANCE-NAME@gitlab-ops.iam.gserviceaccount.com" # Needs to be update to account created in step 2
}

```

## Step 6: Deployment and Validation

### 6.1 Test Atlantis Integration

1. Create a test Terraform change in your target repository
2. Open a merge request
3. Verify that Atlantis automatically runs `terraform plan`
4. Add approval to the merge request
5. Comment `atlantis apply` to test the apply workflow
6. Verify that the infrastructure changes are applied successfully

## Troubleshooting

### Common Issues

1. **"This repo is not allowlisted for Atlantis"**
   - Ensure the repository is added to the `orgAllowlist` configuration
   - Verify the repository path is correct

2. **Missing secrets errors**
   - Check that all required secrets are created in Vault
   - Verify the external secrets configuration is correct
   - Ensure secret paths match between configuration and Vault

3. **Permission denied errors**
   - Verify service account permissions
   - Check that the Atlantis service account can impersonate the target GCP service accounts
   - Review IAM bindings and roles

4. **Webhook not triggering**
   - Verify webhook URL and token configuration
   - Check that the webhook is enabled for the correct events
   - Review GitLab project webhook settings

5. **Service account impersonation errors**
   - Ensure the variable `google_impersonated_account` is properly set in the service account configuration
   - Verify that the hardcoded service account email matches the actual Atlantis service account
   - Check that the service account exists and has proper permissions
