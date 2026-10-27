# GKE cluster upgrade

All our GKE clusters are on the [Regular release channel](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/release-channels) with auto-upgrade enabled. We roll out each new minor version manually **before** the GCP auto-upgrade date to catch breakage early. Node pool upgrades either follow the control-plane bump or auto-run during the next maintenance window.

## Sources of truth

- [GKE release schedule](https://docs.cloud.google.com/kubernetes-engine/docs/release-schedule) — check the auto-upgrade date for each minor.
- [GKE release notes](https://docs.cloud.google.com/kubernetes-engine/docs/release-notes) — GKE-specific patches and known issues.
- [Kubernetes CHANGELOG](https://github.com/kubernetes/kubernetes/tree/master/CHANGELOG) — upstream deprecations and API removals per minor.
- [Kubernetes release blogs](https://kubernetes.io/blog/) — the "What's new" narrative for each minor.
- Previous upgrade issues: [v1.35](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28631), [v1.34](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28159), [v1.33](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/27126).

## Risks

Uncontrolled auto-upgrades can introduce:

- API deprecations preventing workload deployments.
- Workload crashes due to compatibility issues.
- Networking regressions inside clusters.
- Other unforeseen breaking changes.

Manually rolling out ahead of the auto-upgrade date lets us pause on failures without hitting Google's deadline.

## Procedure

### 1. Read the release notes

Read the K8s and GKE release notes for the target version. Pay attention to:

- Removed APIs (see the [Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)).
- Metric renames or removals (check dashboards after upgrade).
- Networking, storage, and scheduler changes.

Grep our manifests for deprecated API versions:

```sh
# In k8s-workloads/gitlab-com and argocd/apps checkouts
git grep -h '^apiVersion:' | sort -u
```

### 2. Confirm the target version

Query GKE for the latest patch of the target minor in the Regular channel:

```sh
gcloud --project gitlab-pre container get-server-config \
  --region us-east1 --format json \
  | jq '.channels[] | select(.channel == "REGULAR")'
```

### 3. Upgrade the control plane

Bump `kubernetes_version` for each cluster in `config-mgmt`. Example: [config-mgmt!9893](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/9893).

Apply via Atlantis in the MR:

```text
atlantis plan -p <env>
atlantis apply -p <env>
```

Wait up to 30 minutes for the control-plane upgrade to complete. Verify:

```sh
gcloud --project <PROJECT> container clusters describe <CLUSTER> \
  --location <LOCATION> --format='value(currentMasterVersion)'
```

### 4. Upgrade node pools

Two options:

**Auto-upgrade during maintenance window** — the default. Node pools upgrade themselves within the cluster's next maintenance window after the control plane. Nothing to do except monitor.

**Manual upgrade** — for large pools or when you want to control timing:

```sh
gcloud container clusters upgrade <CLUSTER> \
  --project=<PROJECT> \
  --location=<LOCATION> \
  --node-pool=<NODE_POOL> \
  --async
```

Repeat for each node pool. Large pools on `ops-gitlab-gke` and `gprd-*` clusters can take several hours per pool.

List pools:

```sh
gcloud --project <PROJECT> container node-pools list \
  --cluster <CLUSTER> --location <LOCATION>
```

### 5. Cluster order

- **Non-production** in parallel: `db-benchmarking-gitlab-gke`, `ops-central`, `pre-gitlab-gke`, `release-gitlab-gke`, staging clusters, subscription clusters.
- **Production** clusters: **CR required**. Upgrade one at a time, spaced across days.

Full inventory used in each quarterly upgrade issue (adjust as clusters are added/removed):

| Project | Cluster |
| --- | --- |
| `gitlab-db-benchmarking` | `db-benchmarking-gitlab-gke` |
| `gitlab-ops` | `ops-central`, `ops-gitlab-gke` |
| `gitlab-pre` | `pre-gitlab-gke` |
| `gitlab-production` | `gitlab-3okls`, `gprd-gitlab-gke`, `gprd-us-east1-{b,c,d}` |
| `gitlab-release` | `release-gitlab-gke` |
| `gitlab-staging-1` | `gitlab-36dv2`, `gstg-gitlab-gke`, `gstg-us-east1-{b,c,d}` |
| `gitlab-subscriptions-prod` | `prdsub-customers-gke` |
| `gitlab-subscriptions-staging` | `stgsub-customers-gke` |
| `gitlab-subscriptions-stg-ref` | `stgsub-ref-customers-gke` |

## Maintenance windows

Windows are defined per cluster in `config-mgmt` under the `maintenance_policy` block (legacy internal module — see [`environments/gprd/gke-regional.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/gke-regional.tf)) or the `maintenance_start_time` / `maintenance_end_time` / `maintenance_recurrence` fields (upstream module — see [`environments/argocd-playground/gke.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/argocd-playground/gke.tf)). Rollouts pause on weekends and holidays.

### Aborted node-pool upgrades

If a node-pool upgrade doesn't finish within the window, GCP "cancels" the current node's upgrade at the end of the window. This is not an incident: the pool ends up mixed-version and GKE resumes the upgrade during the next maintenance window.

Example: an operation aborted at the 08:00 window close:

```text
operation-1617690426743-bb7cc7db  UPGRADE_NODES  us-east1  sidekiq-catchall-1  Operation was aborted:
operation-1617690426743-bb7cc7db  DONE           2021-04-06T06:27:06Z          2021-04-06T08:05:29Z
```

`gcloud container operations list --project <PROJECT>` shows these. Fresh nodes provisioned by the autoscaler during a mixed-version period come up on the old version — expected.

## Post-upgrade

- Verify dashboards under the `kubernetes` folder in <https://dashboards.gitlab.net> still populate.
- Update `kubectl` version in tooling repos ([k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com) `.tool-versions`, [argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps) `.tool-versions`) to match the new minor.
- Check for `KubeServiceApiserverErrorSLOViolation` and scheduling alerts in the days following.

## cgroup v2

- Default from GKE **1.33**.
- cgroup v1 deprecated in Kubernetes 1.31 and removed in 1.35 — see [Migrate to cgroupv2](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/migrate-cgroupv2).
- Node pools inherit their cgroup mode from creation time; **replacing** a node pool is the safe way to switch a legacy pool to v2. See [production-engineering#26079](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/26079) for the completed migration.

## Rollback

There is no in-place downgrade. If a control-plane upgrade breaks things:

1. Open a Sev-1 support case with Google Cloud.
2. For zonal clusters, drain and stop traffic to that cluster from HAProxy (see [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md)) while investigating.
3. In extreme cases, destroy and rebuild the cluster from Terraform — see [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md).

## Related

- [production-engineering#26110 — Automated GKE cluster upgrades](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/26110) — proposal for automation.
