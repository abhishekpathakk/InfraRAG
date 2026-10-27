# Pulp Infrastructure Setup

## Overview

This document describes the step-by-step to setup a Pulp environment (similarly, you can also use it as a
reference when redeploying Pulp on an existing environment).

This guide relies on the current automation and Infrastructure-as-Code (IaC) which are currently used to deploy
Pulp. Thus, it won't go into details about each components or explain infrastructre architect. This is rather a
glue between the existing automation and remaining manual steps we need to do to deploy Pulp.

## Instruction

1. **Terraform setup**: Create a new file in `environments/<env>/pulp.tf` in the `config-mgmt` repository and adapt the values. You can
   refer to
   [`environments/ops/pulp.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ops/pulp.tf)
   as an example. Apply the new environment via a MR.
1. **Create a new database user**:
   - Access the new CloudSQL instance created by Terraform on the GCP Console
   - Go to `Users`
   - Create a new user named `pulp`
   - Note down the password for the next step
1. **Vault setup**: A Pulp setup requires 4 Vault items in the location `k8s/<env>-gitlab-gke/pulp/`:

   - `memorystore`: MemoryStore connection details. It is created by Terraform. Nothing to do here.
   - `gpg`: Create a key `private_key` with the value is a valid private key used for GPG
   - `admin-password`: Create a key `password` with the value is a random string used as Pulp's admin password
   - `db`: Add the folllwing JSON value, in which you only need to update POSTGRES_PASSWORD from the password
     created in the previous step:

      ```json
      {
        "POSTGRES_DB_NAME": "pulp",
        "POSTGRES_HOST": "pulp-sql-proxy",
        "POSTGRES_PASSWORD": "CHANGEME",
        "POSTGRES_PORT": "5432",
        "POSTGRES_SSLMODE": "prefer",
        "POSTGRES_USERNAME": "pulp"
      }
      ```

1. **Helm setup**:
   1. Open the [`argocd/apps` repository](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/pulp)
   1. Copy `services/pulp/env/ops/*.yaml` to `services/pulp/env/<env>/`
   1. Copy `services/pulp/env/ops/clusters/ops-gitlab-gke/app.yaml` to `services/pulp/env/<env>/clusters/<cluster>/app.yaml`
   1. Adapt the Vault secret versions in `services/pulp/env/<env>/values-vault-secrets.yaml`
   1. Replace the `instance` value with the CloudSQL instance name created by Terraform in the previous step in `services/pulp/env/<env>/values-sql-proxy.yaml`
   1. Replace the following values in `services/pulp/env/<env>/values.yaml`:
      - `fqdn`: the full domain name to access the Pulp instance
      - `loadBalancerIP`: Go to the [GCP's IP address
        page](https://console.cloud.google.com/networking/addresses/list?referrer=search), choose the right
        project, and then filter by `pulp-gke-ingress-`. You should find only one result. This is the IP address
        created by Terraform. Use the IP address for `loadBalancerIP`
      - `pulpCert.issuerRef.name`: Depend on the domain name, choose the right SSL certificate issuer. As a rule of
        thumb:
        - `*.gitlab.net`: Use `gitlab-combined`
        - `*.gitlab.com`: Use `cloudflare-issuer`
   1. Apply via an MR

### Testing the setup

Performing the following simple tests to validate if the setup is accessible:

- Access the Pulp instance's domain name
- Create a test repository:

  ```bash
  export PULP_ADMIN_PASSWORD=$(kubectl get secret pulp-custom-admin-password -o jsonpath='{.data.password}' | base64 -d)
  export PULP_DOMAIN=<pulp-domain>
  pulp config create --base-url "https://${PULP_DOMAIN}" --api-root "/pulp/" --verify-ssl --format json --force --username admin --password "${PULP_ADMIN_PASSWORD}" --timeout 0 --overwrite
  pulp deb repository create --name=variant-1-bookworm
  ```
