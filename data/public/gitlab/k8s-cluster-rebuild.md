# Rebuild a GKE cluster

> [!note]
> Covers **replacement** of an existing zonal cluster. To provision a new cluster in a different region, see [k8s-new-cluster.md](k8s-new-cluster.md).

> [!important]
> Rebuilding a staging or production cluster requires a [Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/) with Sr. Infrastructure Manager and Release Manager approval.

This procedure was refined during the July 2025 rebuild of the `gprd` zonal clusters — see [production#20220](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20220), [production#20228](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20228), [production#20229](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20229) and the [retrospective](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/27141).

## Preflight

- **CIDR overlap**: If two VPCs are peered (as `gstg` and `gprd` are today), the new `master_ipv4_cidr_block` must not overlap any subnet in the peer VPC. Check both environments' `variables.tf` in `config-mgmt` before choosing a CIDR — [`environments/gprd/variables.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/variables.tf) and [`environments/gstg/variables.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/variables.tf). See [Cluster network isolation restrictions](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/latest/network-isolation#restrictions_and_limitations).
- **Deletion protection**: production clusters set `deletion_protection = true`. Disable it in a **separate** `config-mgmt` MR before running the `-replace` apply.
- **NetworkPolicies with CIDR selectors**: rebuilt clusters run [Dataplane V2](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2) (Cilium + eBPF), which does not enforce `NetworkPolicy` rules that use CIDR selectors — they silently fail. Grep the workload repos for any and convert them to pod selectors ahead of the rebuild:

    ```sh
    git grep -A2 -B2 'ipBlock:' argocd/apps/ k8s-workloads/gitlab-com/
    ```

    The `gprd` rebuild hit this on the `api` → `registry` and `pages` → `internal-api` paths — see [k8s-workloads/gitlab-com!4601](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests/4601) for the fix pattern.

## 1. Skip cluster deployments

Set `CLUSTER_SKIP` to the target cluster name (for example `gprd-us-east1-b`) in the [`ops` mirror CI variables](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/settings/ci_cd). This pauses `k8s-workloads/gitlab-com` deploys to that cluster. See [`k8s-workloads/gitlab-com` TROUBLESHOOTING § Skipping Cluster Deployments](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/TROUBLESHOOTING.md#skipping-cluster-deployments).

> [!important]
> Remove `CLUSTER_SKIP` after the rebuild.

## 2. Pause monitoring

Create silences on [alerts.gitlab.net](https://alerts.gitlab.net/):

- Cluster alerts: `env="gprd" cluster="gprd-us-east1-b"`
- Traffic cessation: `alert_class="traffic_cessation" env="gprd" region="us-east1-b"`

## 3. Drain traffic from the zonal cluster

Gracefully stop all HAProxy nodes in the same zone as the target cluster. `SIGUSR1` tells HAProxy to stop accepting new connections and drain existing ones — the default `systemctl stop` sends `SIGTERM`, which closes connections immediately.

```sh
zone=b   # target zone

knife ssh -C 5 "chef_environment:gprd AND roles:gprd-base-haproxy AND zone:projects\\/805818759045\\/zones\\/us-east1-$zone" \
  'sudo systemctl mask haproxy.service; \
   sudo systemctl kill --signal SIGUSR1 haproxy.service; \
   while [ $(systemctl is-active haproxy.service) != "inactive" ] && [ ${i:=1} -lt 150 ]; do sleep 2; i=$((i + 1)); done; \
   sudo systemctl stop haproxy.service; \
   systemctl status haproxy.service; \
   sleep 30'
```

Verify from the [HAProxy dashboard](https://dashboards.gitlab.net/d/haproxy/haproxy) that traffic to `us-east1-<zone>` backends has ceased before proceeding.

The alternative, draining per backend row through [consul KV](../frontend/agent.md#draining-a-server), is one `consul kv put` per row from a console node (11 rows per zone in gprd) and applies within seconds; when this section was written the tooling drained over ssh to every load balancer and was too slow for a rebuild. Bulk `systemctl mask` per zone remains the documented approach here.

## 4. Replace the cluster

### 4a. Disable deletion protection

Open a `config-mgmt` MR setting `deletion_protection = false` on the target cluster. Get it merged before starting the replace.

### 4b. Replace via Atlantis

Open a `config-mgmt` MR with the desired changes to the zonal cluster module. See [config-mgmt!11519](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/11519) as an example.

Get the MR approved but **do not merge**.

Plan the replace:

```text
atlantis plan -p gprd -- -replace module.gke-us-east1-b.google_container_cluster.cluster
```

The plan should show:

```text
Terraform will perform the following actions:

  # module.gke-us-east1-b.google_container_cluster.cluster will be replaced, as requested

  ...

  # module.gke-us-east1-b.google_container_node_pool.node_pool["generic-1"] will be replaced due to changes in replace_triggered_by
```

Apply without auto-merge:

```text
atlantis apply -p gprd --auto-merge-disabled
```

Cluster and node pool creation takes 20–30 minutes.

### 4c. Update Vault

Run the `vault-production` plan and apply to update the Kubernetes auth method and secret engine with the new cluster IP and CA certificate:

```text
atlantis plan -p vault-production
atlantis apply -p vault-production
```

Atlantis will auto-merge on success.

### 4d. Collect the new reserved IPs

```sh
gcloud compute addresses list --project gitlab-production | grep -E '(ai-assisted|api|git-https|nginx|pages|registry|ssh|web|websockets)-gke-gprd-us-east1-b'
```

### 4e. Update HAProxy backend IPs

In [`chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo), open an MR replacing the backend server IPs for the target zone with the new IPs collected above:

```yaml
# roles/gprd-base-haproxy-main-config.json
"api-gke-us-east1-b":         "<nginx-gke-gprd-us-east1-b>"
"web-gke-us-east1-b":         "<web-gke-gprd-us-east1-b>"
"shell-gke-us-east1-b":       "<ssh-gke-gprd-us-east1-b>"
"ws-gke-us-east1-b":          "<websockets-gke-gprd-us-east1-b>"
"ai-assisted-gke-us-east1-b": "<ai-assisted-gke-gprd-us-east1-b>"
"git-https-gke-us-east1-b":   "<git-https-gke-gprd-us-east1-b>"

# roles/gprd-base-haproxy-registry.json
"registry-us-east1-b": "<registry-gke-gprd-us-east1-b>"

# roles/gprd-base-haproxy-pages.json
"pages-us-east1-b": "<pages-gke-gprd-us-east1-b>"
```

Get the MR merged. Run `chef-client` on all HAProxy nodes in the background:

```sh
knife ssh -C 10 'chef_environment:gprd AND roles:gprd-base-haproxy' 'sudo chef-client'
```

### 4f. Update service LB IPs in `k8s-workloads/gitlab-com`

Open a `k8s-workloads/gitlab-com` MR updating the service LoadBalancer IPs for the target zone with the new IPs. **Do not merge yet** — this depends on cluster workloads being ready first.

## 5. Configure kubectl for the new cluster

```sh
gcloud container clusters get-credentials gprd-us-east1-b --project gitlab-production --location us-east1-b
# or
glsh kube setup
glsh kube use-cluster gprd-us-east1-b
kubectl get pods --all-namespaces
```

Confirm the cluster Secret in [`argocd/config`](https://gitlab.com/gitlab-com/gl-infra/argocd/config) still exists and has the expected labels (`gitlab.com/environment`, `gitlab.com/k8s-cluster-name`). ArgoCD ApplicationSets use these labels to fan applications out.

## 6. Deploy platform workloads via ArgoCD

Platform services (Vault, Prometheus, Mimir, KEDA, cert-manager, external-dns, and everything else previously in `gitlab-helmfiles`) are managed by ArgoCD. Once the cluster is reachable and its ArgoCD Secret is in place, ApplicationSets pick up the new cluster automatically.

From the [ArgoCD UI](https://argocd.gitlab.net/), filter applications by the rebuilt cluster and:

1. Confirm `vault-k8s-secrets` has synced. If it has not, trigger a manual sync.
2. Retrieve the newly-provisioned JWT token from the cluster and save it into Vault so the Kubernetes auth backend can authenticate workloads:

    ```sh
    kubectl --namespace vault-k8s-secrets get secret vault-k8s-secrets-token -o jsonpath='{.data.token}' | base64 -d | \
      vault kv put ci/ops-gitlab-net/gitlab-com/gl-infra/config-mgmt/vault-production/kubernetes/clusters/gprd/gprd-us-east1-b service_account_jwt=-
    ```

3. Trigger a new [`config-mgmt` pipeline for the `vault-production` environment](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/pipelines/new?ref=main&var[ENV]=vault-production) to update the Kubernetes secrets engine with the new JWT.
4. Trigger a sync on any remaining ArgoCD applications that have not converged yet. Wait until all report `Healthy` and `Synced`.
5. `kubectl get pods --all-namespaces` and confirm no `CrashLoopBackOff` or `ImagePullBackOff` states.

## 7. Deploy the GitLab chart

1. Remove `CLUSTER_SKIP` from the [`ops` mirror CI variables](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/settings/ci_cd).
2. Merge the `k8s-workloads/gitlab-com` MR from step 4f (service LB IPs).
3. Find the latest pipeline that performed a configuration change to the target environment ([most recent merged MR](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests/?sort=merged_at_desc&state=merged&first_page_size=20) is usually easiest) and re-run its apply job for the rebuilt cluster.

    > This installs releases and configurations but not the current GitLab version.

4. Deploy the correct GitLab version:
    - Look up the latest successful `auto-deploy` job for the target environment in the [`#announcements` Slack channel](https://gitlab.enterprise.slack.com/archives/C8PKBH3M5).
    - Retry the `kubernetes-<env>` trigger job on that pipeline.

5. Spot-check:

    ```sh
    glsh kube use-cluster gprd-us-east1-b
    kubectl get pods --namespace gitlab
    ```

6. Verify version parity across zonal clusters:

    ```sh
    for c in gprd-us-east1-{b,c,d}; do
      glsh kube use-cluster "$c"
      echo -n "$c: "
      kubectl get configmap --namespace gitlab gitlab-gitlab-chart-info -o jsonpath='{.data.gitlabVersion}'
      echo
    done
    ```

## 8. Resume monitoring

- Check the [cluster-numbers dashboard](https://dashboards.gitlab.net/goto/1G_u458NR) — pod and container counts for the rebuilt cluster.
- Remove any silences created earlier.
- Verify no alerts firing for the rebuilt cluster in [Alertmanager](https://alerts.gitlab.net).

## 9. Restore traffic

Restart HAProxy nodes one at a time, 30 seconds apart, to give the cluster time to scale as traffic returns:

```sh
zone=b

knife ssh -C 1 "chef_environment:gprd AND roles:gprd-base-haproxy AND zone:projects\\/805818759045\\/zones\\/us-east1-$zone" \
  'sudo systemctl unmask haproxy.service; \
   sudo systemctl start haproxy.service; \
   systemctl status haproxy.service; \
   sleep 30'
```

Verify from the HAProxy dashboard that traffic has resumed.

## Known caveats

- **Control plane resize during initial GitLab deployment**: during the first `gprd` rebuild, `pdcsi-node` pods crashlooped for close to an hour because the API server was intermittently unavailable. The cause was an automatic [GKE control plane resize](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/regional-clusters#control_plane_management) triggered by the sudden surge in API load from deploying the full GitLab chart into an empty cluster. Zonal clusters run a single-replica control plane and briefly become unavailable during resizes ([Planning cluster scalability](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/planning-scalability#control_plane_availability)). The problem resolved itself once the resize completed. If you see new nodes stuck `NotReady` with API-timeout logs, check the [cluster's operations](https://docs.cloud.google.com/kubernetes-engine/docs/troubleshooting) for an in-progress `UPGRADE_MASTER` or `RESIZE_CLUSTER` and wait it out.
- **Calico legacy clusters**: `gprd-gitlab-gke` and `gstg-gitlab-gke` still run Calico. Their rebuild is tracked under [&1651](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/1651).

## Rollback

There is no rollback once the cluster is destroyed. If HAProxy has been drained but the Atlantis apply has not started, restart HAProxy per [step 9](#9-restore-traffic) to restore traffic and abort. Once `atlantis apply` runs, the only path is forward.

## Related

- [k8s-new-cluster.md](k8s-new-cluster.md) — provisioning a fresh cluster.
- [k8s-cluster-upgrade.md](k8s-cluster-upgrade.md) — control-plane and node-pool version bumps.
- [kube-administration.md](kube-administration.md) — CA rotation.
- [production#20229 — 2025-07-31 rebuild CR](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20229) — most recent full example.
- [production-engineering#27141 — rebuild retrospective](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/27141).
