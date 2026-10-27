# Troubleshooting Hashicorp Vault

## Determining Pod status and logs

Connect to the appropriate GKE cluster, then list/look at all pods in the `vault` namespace:

```shell
kubectl -n vault get pods
kubectl -n vault logs vault-0
```

The active node can be found with the label `vault-active=true`:

```shell
kubectl -n vault get pods -l app.kubernetes.io/name=vault -l vault-active=true
```

## Determining status of Vault from Vault itself

You can use a SOCKS5 proxy or forward the port `8200` and run Vault locally (see [CLI](usage.md#cli)):

```shell
# In a separate shell session
ssh -D 18200 bastion-01-inf-ops.c.gitlab-ops.internal
# In your first session
export VAULT_ADDR=https://vault.ops.gke.gitlab.net
export VAULT_PROXY_ADDR=socks5://localhost:18200
vault login -method oidc role=admin
vault operator peers
vault operator raft list-peers
# Ensure all Vault pods are listed and their `State` is either `leader` or `follower`
```

```shell
# In a separate shell session
kubectl -n vault port-forward svc/vault-active 8200
# In your first session
export VAULT_ADDR=https://localhost:8200
export VAULT_TLS_SERVER_NAME=vault.ops.gke.gitlab.net
vault login -method oidc role=admin
vault operator peers
vault operator raft list-peers
# Ensure all Vault pods are listed and their `State` is either `leader` or `follower`
```

Alternatively, you can connect to one of the Vault pods and run:

```shell
kubectl -n vault exec -it vault-0 sh
$ vault status
$ export VAULT_SKIP_VERIFY=true
# Ensure `Initialized` is `true` and `Sealed` is `false`
$ vault login
# enter root token
$ vault operator peers
$ vault operator raft list-peers
# Ensure all Vault pods are listed and their `State` is either `leader` or `follower`
```

## No Active Vault Instance / Vault Sealed / Vault Low Failure Tolerance

The Vault pods are failing to start, have lost quorum or are unable to auto-unseal.

Vault is deployed in a cluster of 5 nodes, so it needs at least 3 healthy nodes to have a quorum and be operational.

Check the status of the Vault deployment and investigate any failing pod for errors:

```sh
kubectl --namespace vault get pods
kubectl --namespace vault logs vault-X
```

You can also [check the logs in Elasticsearch](https://nonprod-log.gitlab.net/goto/225b16e0-0687-11ed-af31-918941b0065a) instead.

In case of unseal errors:

- Verify that the Kubernetes Service Account is still associated to its Google Service Account `vault-ops-k8s@gitlab-ops.iam.gserviceaccount.com`:

  ```sh
  kubectl --namespace vault describe serviceaccount vault
  ```

- Verify that this Service Account has permission to use the [unseal KMS key](https://console.cloud.google.com/security/kms/key/manage/global/gitlab-vault-vault-production/vault-vault-production-unseal-key;tab=overview?project=gitlab-vault-production) for encryption/decryption.

### In case of individual node failures

There is no fixed procedure — diagnose from pod state and logs, then pick the appropriate branch below:

- **Zonal outage.** The Vault [topology spread constraints](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/vault/values.yaml) require pods to be spread across 3 zones. Pods in the affected zone should reschedule automatically on nodes in the remaining zones. If they don't, check node availability in the affected zone, the PodDisruptionBudget, and pending-pod events (`kubectl -n vault describe pod vault-X`).

- **Storage corruption after an unclean shutdown.** If a pod fails to start with Raft/BoltDB corruption errors in its logs, delete its PVC and kill the pod to force reinitialisation from a fresh Raft snapshot:

  ```shell
  kubectl -n vault delete pvc data-vault-X
  kubectl -n vault delete pod vault-X
  ```

  This is the same operation the [`vault-pvc-rotater`](vault.md#vault-pvc-rotater) CronJob performs on a weekly rotation.

- **Cluster rejoin or leader-election failures.** Check the failing pod's logs for Raft errors. From a healthy pod, run `vault operator raft list-peers` and `vault operator raft autopilot state` to see how the cluster views the failing node. Verify pod-to-pod network connectivity on port `8201` (Raft cluster port) if peers are not reachable.

## Vault Audit Log Request Failure

Vault is unable to send its audit log and thus has stopped all operations until it is able again.

At the time of this writing, [the Vault audit logs are written directly to `stdout`](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/vault/vault-configuration/-/blob/main/audit.tf), so they can be collected by Fluentd and shipped to Elasticsearch, which makes failure extremely unlikely.

If Vault fails to write its audit logs it could mean:

- a bug introduced in Vault: has it been upgraded recently? Search the [issues on GitHub](https://github.com/hashicorp/vault/issues).
- `containerd` not able to handle the container's output, possibly affecting other workloads, check the health of node running the active Vault pod.

## Debugging CI Vault permission errors

Vault access from CI has several layers of configuration ([`infra-mgmt`](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt), [`config-mgmt/environments/vault-production`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production), the [`vault-configuration`](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/vault/vault-configuration) Terraform module, and Vault itself) and it can be difficult to reason about which one is failing when a permission error is reported. Follow the steps below in order to narrow it down.

1. **Verify the secret actually exists at the expected path**, and fix on the writer side (Terraform outputs, manual `vault kv put`, or External Secrets Operator sync) if it doesn't:

   ```shell
   vault kv metadata get <mount>/<full-path>
   ```

2. **Verify the project role in `infra-mgmt`.**
   The project must have `vault = { enabled = true, auth_path = local.vault_auth_path }` in its module definition. If the secret is outside the project's default paths (`ci/<instance>/<full-path>/*`), the project must additionally list it in one of `readonly_secret_paths`, `readwrite_secret_paths`, `protected_secret_paths`, `extra_readonly_policies`, or `extra_protected_policies`. See [`terraform-modules/gitlab/project`](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/gitlab/project) for the full input schema.

3. **Verify the role config and policies in Vault directly.**

   ```shell
   vault read auth/<gitlab-instance>/role/<project-path-underscores>
   vault read auth/<gitlab-instance>/role/<project-path-underscores>-rw
   vault policy read <gitlab-instance>-project-<project-path-underscores>
   vault policy read <gitlab-instance>-project-<project-path-underscores>-rw
   ```

   Confirm that:
   - `bound_claims` contains the correct `project_id` (and `ref_protected = "true"` for the `-rw` role);
   - `token_policies` lists the expected policies;
   - each policy grants the required capabilities on the target path.

   If the role or policies don't match what `infra-mgmt` should have created, run the Atlantis plan/apply on the `infra-mgmt` MR — the drift may simply not have been applied.

4. **Confirm the CI job's ID token audience and JWT claims.**
   The job must define:

   ```yaml
   id_tokens:
     VAULT_ID_TOKEN:
       aud: https://vault.gitlab.net
   ```

   and use the expected `VAULT_AUTH_ROLE` / `VAULT_AUTH_PATH` values (set on the project or group). See [Using Vault secrets in CI](usage.md#using-vault-secrets-in-ci).

5. **For writes from Atlantis** (Terraform-triggered `vault_kv_secret_v2` resources), verify that Atlantis itself has the right to write to the target path. Atlantis's own policy is defined in [`environments/vault-production/secrets_policies.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production/secrets_policies.tf); if the Atlantis project doesn't have write access to the path, the apply will fail with a permission error even though the *user* running the pipeline has access via OIDC.

Cross-references: [access.md](access.md) (Okta groups), [administration.md](administration.md) (adding a GitLab instance or Kubernetes cluster), [usage.md#authorizing-a-gitlab-project](usage.md#authorizing-a-gitlab-project).

## Debugging External Secrets Operator (ESO) / Kubernetes secret delivery breakage

When an `ExternalSecret` in a Kubernetes namespace stops syncing (or never populates), work through the following in order:

1. **Confirm the secret exists at the configured path in Vault**:

   ```shell
   vault kv metadata get <mount>/<full-path>
   # e.g. vault kv metadata get k8s/<cluster>/<namespace>/<secret>
   # or   vault kv metadata get shared/...
   ```

   Fix on either side if the path doesn't match.

2. **Check the ESO role in [`environments/vault-production/kubernetes.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/vault-production/kubernetes.tf)**, under `kubernetes_clusters.<cluster>.auth_roles` (used by the External Secrets Operator to authenticate) and/or `secrets_roles` (for dynamic Kubernetes credentials). Add or fix it if missing.

3. **Read the role directly from Vault** to confirm what actually got applied:

   ```shell
   vault read auth/kubernetes/<cluster>/role/<role>
   ```

   Fix drift in Terraform if the role config doesn't match expectations.

4. **Inspect the policies attached to the role**:

   ```shell
   vault policy read <policy-name>
   # e.g. vault policy read k8s_<cluster>_<role>
   ```

   The default policy attached to an ESO auth-role is `k8s_<cluster>_<role>` (single underscore separator). This is distinct from Kubernetes secrets-engine role policies, which follow `kubernetes_<cluster>--<role>` (see [`usage.md`](usage.md#add-kubernetes-roles-in-vault)).

5. **Recovering from a misconfigured secret value**:
   - If the user wrote the wrong value: `vault kv patch` with the correct value, or roll back by pinning `version` in the `ExternalSecret` spec to a previous version.
   - If the secret was `destroy`ed entirely (versioning history lost): the user must recreate it as a new secret.

## Generating a root token

Official documentation: <https://learn.hashicorp.com/tutorials/vault/generate-root>

When `admin` access is not sufficient or broken, a root token can be generated using the recovery keys. For this you will need access to the entry `Vault Production` in the `Production` vault in 1password.

**:warning: Root tokens are dangerous as they allow to do anything in the cluster and don't expire. For this reason, please remember to revoke it using `vault token revoke -self` once you are done using it! :warning:**

- First, setup CLI access by following the steps described [here](usage.md#cli)
- Verify that Vault is unsealed:

  ```shell
  vault status
  ```

  If not, [troubleshoot the issue](#determining-status-of-vault-from-vault-itself)
- Grab 3 recovery keys of the 5, and run the following:

  ```shell
  vault operator generate-root -init
  # Note the OTP in the output
  vault operator generate-root
  # Enter recovery key #1
  vault operator generate-root
  # Enter recovery key #2
  vault operator generate-root
  # Enter recovery key #3
  # The output should now show "Complete true"
  # Grab the Encoded Token from the output and the OTP from the first step and run:
  vault operator generate-root -decode $ENCODED_TOKEN -otp $OTP
  # The output is your root token, now you can export it:
  export VAULT_TOKEN=hvs.thetokenfromabove
  vault token lookup
  # This should show something like this:
  # Key                 Value
  # ---                 -----
  # accessor            XYZ
  # creation_time       1658469449
  # creation_ttl        0s
  # display_name        root
  # entity_id           n/a
  # expire_time         <nil>
  # explicit_max_ttl    0s
  # id                  hvs.thetokenfromabove
  # meta                <nil>
  # num_uses            0
  # orphan              true
  # path                auth/token/root
  # policies            [root]
  # ttl                 0s
  # type                service
  ```

- When you are done troubleshooting, please revoke the token:

  ```shell
  vault token revoke -self
  ```

## Backing up and restoring Vault

Vault Raft snapshots are taken hourly. They are created by a Kubernetes [CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/) that runs inside the GKE cluster that runs Vault. It uses [vault operator raft snapshot save](https://developer.hashicorp.com/vault/docs/commands/operator/raft#snapshot-save) to create an encrypted copy of all Vault data, and then uploads to it to a GCS bucket inside a separate GCP project:

- Production: [`gitlab-vault-production-vault-raft-snapshots`](https://console.cloud.google.com/storage/browser/gitlab-vault-production-vault-raft-snapshots?project=gitlab-vault-production) in `gitlab-vault-production`
- Staging: [`gitlab-vault-staging-vault-raft-snapshots`](https://console.cloud.google.com/storage/browser/gitlab-vault-staging-vault-raft-snapshots?project=gitlab-vault-staging) in `gitlab-vault-staging`

### Restoring Vault from a snapshot into an existing functional installation

Note that doing this restores everything entirely back to the state it was at the snapshot, removing all new data since the snapshot was taken.

- First identify the Vault snapshot you wish to restore and download it locally:

  ```shell
  gsutil ls gs://gitlab-vault-production-vault-raft-snapshots/
  gsutil cp gs://gitlab-vault-production-vault-raft-snapshots/2022/07/22/raft-20220722-120000+0000.snap .
  ```

- Then, setup CLI access by following the steps described [here](usage.md#cli)
- Then [generate a root token](#generating-a-root-token)
- Restore the snapshot:

  ```shell
  vault operator raft snapshot restore raft-20220722-120000+0000.snap
  ```

- :warning: Finally, don't forget to revoke your root token!

  ```shell
  vault token revoke -self
  ```

### Restoring Vault from a snapshot into an empty installation

:warning: As we use GKMS auto-unseal for our Vault, you need to make sure the
GKMS key that was originally used with the Vault snapshot is still available. As
this is controlled by Google, they are responsible for maintaining its snapshot
and availability. :warning:

- First identify the Vault snapshot you wish to restore and download it locally:

  ```shell
  gsutil ls gs://gitlab-vault-production-vault-raft-snapshots/
  gsutil cp gs://gitlab-vault-production-vault-raft-snapshots/2022/07/22/raft-20220722-120000+0000.snap .
  ```

- Make sure the [Vault application in ArgoCD](https://argocd.gitlab.net/applications/argocd/vault--a1ea8) is synced.
- You should see the Vault pods running and crashing in a loop (because they are uninitialized and don't have a cluster to join):

  ```shell
  kubectl -n vault get pods
  ```

- Scale down the cluster to a single pod so that replication doesn't start until the snapshot has been restored:

  ```shell
  kubectl -n vault scale sts/vault --replicas=1
  ```

- To make the following steps easier, edit `failureThreshold` of the healthchecks to some high number in the StatefulSet to prevent the unhealthy pod from restarting before you initialize it:

  ```shell
  kubectl -n vault edit sts vault
  # livenessProbe:
  #   failureThreshold: 1000
  # readinessProbe:
  #   failureThreshold: 1000
  ```

  > [!note]
  > Note the previous values so you can restore them later; at the time of writing they are `livenessProbe.failureThreshold: 30` and `readinessProbe.failureThreshold: 3` (see [`services/vault/values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/b25b54707ca3431dd697eaf810ed52a2cbc9cb6b/services/vault/values.yaml#L53-67)).

- In a separate shell session, establish port-forwarding to the pod:

  ```shell
  # In a separate shell session
  kubectl -n vault port-forward pod/vault-0 8200
  ```

- Then initialize Vault, take note of the root token and export it (no need to save it elsewhere, it will be gone after the snapshot restoration):

  ```shell
  # In your first session
  export VAULT_ADDR=https://localhost:8200
  export VAULT_TLS_SERVER_NAME=vault.ops.gke.gitlab.net
  vault operator init
  export VAULT_TOKEN=hvs.something
  ```

- Now you can force-restore the snapshot:

  ```shell
  vault operator raft snapshot restore -force raft-20220722-120000+0000.snap
  ```

- Check in the pod logs that Vault was able to restore and unseal:

  ```shell
  kubectl -n vault logs vault-0
  ```

- You can now restore `failureThreshold` to its original values in the StatefulSet (see the note above for the current defaults):

  ```shell
  kubectl -n vault edit sts vault
  # livenessProbe:
  #   failureThreshold: 30
  # readinessProbe:
  #   failureThreshold: 3
  ```

- And scale back to 5 replicas:

  ```shell
  kubectl -n vault scale sts/vault --replicas=5
  ```

- You should now see the other pods spin up and become healthy, as they will join the Vault cluster and start replicating automatically:

  ```shell
  kubectl -n vault get pods
  ```

- To verify that the cluster is healthy, login as `admin` (or [generate a root token](#generating-a-root-token)) and then:

  ```shell
  vault login -method=oidc role=admin
  vault operator peers
  vault operator raft list-peers
  vault operator raft autopilot state
  ```
