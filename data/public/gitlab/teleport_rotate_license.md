# Updating Enterprise License

When our license is about to expire, we need to obtain a new license file and update our Teleport instances.

## Pre-requisites

- Access to Teleport's billing dashboard at [gitlab-tp.teleport.sh](https://gitlab-tp.teleport.sh/), or support from an admin to download and provide the license for you (see step 1 below).
- [Access to Vault](https://runbooks.gitlab.com/vault/access/)
- Read/write access to the following Vault paths: `k8s/ops-gitlab-gke/teleport-cluster-staging/`, `k8s/ops-central/teleport-cluster-production/`
- [Access to the Kubernetes API](https://runbooks.gitlab.com/kube/k8s-oncall-setup/#kubernetes-api-access), or support from a site reliability or infrastructure engineer to access Kubernetes on your behalf.

## Process

### Step 1. Retrieve the new license

Log in to Teleport's billing dashboard at [gitlab-tp.teleport.sh](https://gitlab-tp.teleport.sh/) as an admin and download the new license file (`license.pem`).

Notes:

- We use the same License for both [staging](https://staging.teleport.gitlab.net)
and [production](https://production.teleport.gitlab.net) instances teleport.
- If you don't have an account, ask an admin user to do so and share the license file with you through a secure channel (e.g. *1Password*). Admin users include the business owners listed in the [tech stack](https://helplab.gitlab.systems/esc?id=gitlab_cmdb_applications) - filter for "Teleport".

### Step 2. Update the license stored in Vault

**Approach 1: via Vault GUI**

1. Log in to vault and navigate to the Teleport cluster

**Staging:** [ops-gitlab-gke/teleport-cluster-staging/](https://vault.gitlab.net/ui/vault/secrets/k8s/kv/list/ops-gitlab-gke/teleport-cluster-staging/)
**Production:** [ops-central/teleport-cluster-production/](https://vault.gitlab.net/ui/vault/secrets/k8s/kv/list/ops-central/teleport-cluster-production/)

1. Click on `license`
2. Click on the `Secret` tab
3. Click `Create new version +`
4. Delete the contents of the text box to the right of `license.pem`, and paste the full contents of the license file obtained in Step 1
5. Click the `Show diff` toggle and confirm the contents have changed
6. Click Save
7. Take note of the `Current version`

**Approach 2: via Vault CLI**

1. Open SSH proxy

```bash
# Run this command from the runbooks repo
$ glsh vault proxy
```

2. Update the license

**Staging:**

```bash
# Write the new license to Vault
$ vault login -method oidc
$ vault kv put k8s/ops-gitlab-gke/teleport-cluster-staging/license license.pem=@license.pem
```

**Production:**

```bash
# Write the new license to Vault
$ vault login -method oidc
$ vault kv put k8s/ops-central/teleport-cluster-production/license license.pem=@license.pem
```

### Step 3. Update Helm chart

Update the `version` for `secretKey:license.pem` in the `argocd` repository:

**Staging:** [services/teleport-cluster/env/ops/clusters/ops-central/values-vault-secrets.yaml](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/env/ops/clusters/ops-central/values-vault-secrets.yaml?ref_type=heads)
**Production:** [services/teleport-cluster/env/ops/clusters/ops-gitlab-gke/values-vault-secrets.yaml](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/env/ops/clusters/ops-gitlab-gke/values-vault-secrets.yaml?ref_type=heads)

### Step 4. Restart the Teleport Auth Service

The auth service should automatically restart after merging the Helm chart changes from the previous step.

If this does not happen, it can be manually restarted by following these steps:

**Staging:**

```bash
# Run this command from the runbooks repo
$ glsh kube use-cluster ops

# Restart the teleport auth pods
$ kubectl rollout restart deployment/teleport-staging-auth --namespace=teleport-cluster-staging
```

**Production:**

```bash
# Run this command from the runbooks repo
$ glsh kube use-cluster ops-central

# Restart the teleport auth pods
$ kubectl rollout restart deployment/teleport-production-auth --namespace=teleport-cluster-production
```

## More information

Read more about the *Enterprise License file* [here](https://goteleport.com/docs/choose-an-edition/teleport-enterprise/license/) and managing it [here](https://goteleport.com/docs/admin-guides/deploy-a-cluster/license/).

Past license rotation issues:

- [Jan 2026](https://gitlab.com/gitlab-com/gl-security/product-security/infrastructure-security/infrastructure/-/work_items/28)
- [Dec 2024](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/26042)

## Troubleshooting

If the license hasn't updated as expected after bumping the secret version, first check that the `license` secret contains what you expect:

```sh
kubectl get secrets license -n teleport-cluster-production -o json | jq -r '.data."license.pem"' | base64 -d
```

If it doesn't, check what the `refreshInterval` of the `ExternalSecret` is:

```sh
kubectl get es license -n teleport-cluster-production -o json | jq .spec.refreshInterval
```

If `refreshInterval` is set to `0`, `external-secrets` will _never_ update the secret from Vault, so you will need to change the `refreshInterval` to something non-zero (e.g. `1h`).
