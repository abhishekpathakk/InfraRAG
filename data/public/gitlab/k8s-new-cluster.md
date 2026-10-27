# Provision a new GKE cluster

This runbook covers provisioning a new GKE cluster from scratch, wiring it into ArgoCD, and registering it with Vault. To **replace** an existing cluster, see [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md).

For production clusters, a [Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/) with Sr. Infrastructure Manager and Release Manager approval is required.

## Terraform module

New clusters use the **upstream** [`terraform-google-modules/kubernetes-engine/google//modules/private-cluster-update-variant`](https://registry.terraform.io/modules/terraform-google-modules/kubernetes-engine/google/latest/submodules/private-cluster-update-variant) module. The [legacy internal module](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/google/gke) is only kept for the older `gprd`/`gstg` regional and zonal clusters and is not used for new work.

Working references in `config-mgmt`:

- Zonal cluster (`private-cluster-update-variant`): [`environments/argocd-playground/gke.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/argocd-playground/gke.tf)
- Regional cluster (`private-cluster-update-variant`): [`environments/observability/gke.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/observability/gke.tf)
- Regional cluster (`private-cluster`): [`environments/pre/gke-regional.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/pre/gke-regional.tf) — `pre-gitlab-gke`

### Attribute differences vs the legacy internal module

If you have been working with the internal module, note these renames in the upstream module:

| Internal (legacy) | Upstream |
| --- | --- |
| `project` | `project_id` |
| `vpc` | `network` |
| `ip_cidr_range` (creates subnet) | `subnetwork` (name of pre-existing subnet) |
| `pod_ip_cidr_range` (creates range) | `ip_range_pods` (name of secondary range) |
| `service_ip_cidr_range` (creates range) | `ip_range_services` (name of secondary range) |
| `private_master_cidr` | `master_ipv4_cidr_block` |
| `regional_cluster = false` + `zone = "..."` | `regional = false` + `zones = ["..."]` |
| `authorized_master_access` | `master_authorized_networks` |
| Per-pool `node_auto_upgrade` | Per-pool `auto_upgrade` |
| Per-pool `min_node_count` / `max_node_count` | Per-pool `min_count` / `max_count` |
| `node_pools = <map>` | `node_pools = <list of maps>` |
| Output `module.x.cluster_name` | Output `module.x.name` |
| Output `module.x.cluster_endpoint` | Output `module.x.endpoint` |
| Output `module.x.cluster_ca_certificate` | Output `module.x.ca_certificate` |
| `maintenance_policy = { ... }` block | `maintenance_start_time`, `maintenance_end_time`, `maintenance_recurrence` (strings) |

### Required settings

New clusters must have:

- `datapath_provider = "ADVANCED_DATAPATH"` — enables [Dataplane V2](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2) (Cilium + eBPF).
- `network_policy = false` — network policies are enforced natively by Dataplane V2; setting this to `true` deploys Calico instead and conflicts.
- `release_channel = "REGULAR"`.
- `kubernetes_version` pinned to a current supported minor (see [supported versions](https://docs.cloud.google.com/kubernetes-engine/docs/release-schedule)).
- `enable_private_nodes = true` and `enable_shielded_nodes = true`.
- `deletion_protection = true` — mandatory for production clusters.

cgroup v2 is the default from GKE 1.33 — no explicit configuration required.

### Preflight: CIDR overlap

If two VPCs are peered (`gstg` and `gprd` are peered today for historic reasons), the `master_ipv4_cidr_block` must not overlap any subnet in the peer VPC or GKE cluster creation fails with:

```text
Error: Error waiting for creating GKE cluster: Conflicting IP cidr range: New subnetwork overlaps with an IP range (172.16.0.16/28) in one of the active peers of an active peer (peering-gstg).
```

See [Cluster network isolation restrictions](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/latest/network-isolation#restrictions_and_limitations).

### Example: zonal cluster

Adapted from [`environments/argocd-playground/gke.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/argocd-playground/gke.tf). Substitute your subnet, project, and cluster name.

```hcl
module "gke-<name>" {
  depends_on = [
    google_compute_network.network,
    google_compute_subnetwork.subnetwork,
  ]

  source  = "terraform-google-modules/kubernetes-engine/google//modules/private-cluster-update-variant"
  version = "44.2.0"

  name       = local.gke_cluster_name
  project_id = var.project

  deletion_protection = true
  release_channel     = "REGULAR"
  kubernetes_version  = "1.33"

  regional = false
  region   = var.region
  zones    = [local.gke_cluster_zone]

  network           = google_compute_network.network.name
  subnetwork        = google_compute_subnetwork.subnetwork.name
  ip_range_pods     = "${local.gke_cluster_name}-pods"
  ip_range_services = "${local.gke_cluster_name}-services"

  enable_private_endpoint = false
  enable_private_nodes    = true
  enable_shielded_nodes   = true

  master_ipv4_cidr_block     = "10.0.0.0/28"
  master_authorized_networks = local.gke_authorized_master_access

  datapath_provider = "ADVANCED_DATAPATH"
  network_policy    = false

  create_service_account   = true
  remove_default_node_pool = true

  node_pools = [
    {
      name               = "spot-nodes-1"
      machine_type       = "n4d-standard-2"
      min_count          = 0
      initial_node_count = 0
      max_count          = 10
      image_type         = "COS_CONTAINERD"
      disk_size_gb       = 100
      disk_type          = "hyperdisk-balanced"
      auto_repair        = true
      auto_upgrade       = true
      autoscaling        = true
      spot               = true
    },
  ]

  node_pools_labels = {
    all = {
      stage = "main"
      type  = "kube"
    }
  }

  node_pools_taints = {
    all = []
    spot-nodes-1 = [
      { key = "cloud.google.com/gke-spot", value = "true", effect = "NO_SCHEDULE" },
    ]
  }
}
```

For a regional cluster, set `regional = true` and drop `zones`.

## Apply via Atlantis

MRs to `config-mgmt` are applied by [Atlantis](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/README.md#atlantis). See the [`config-mgmt` HOWTO](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/HOWTO.md) for the MR workflow.

```text
atlantis plan -p <env>
atlantis apply -p <env>
```

Cluster creation takes 20–30 minutes.

## Post-creation

### 1. Register with Vault

Add a `vault-gke-cluster-info` module block that consumes the cluster outputs, then apply in the `vault-production` environment:

```hcl
module "gke-<name>-vault-cluster-info" {
  source = "../../modules/vault-gke-cluster-info"

  environment                = var.environment
  gke_cluster_name           = module.gke-<name>.name
  gke_cluster_ca_certificate = module.gke-<name>.ca_certificate
  gke_cluster_endpoint       = module.gke-<name>.endpoint
}
```

Note the upstream module attribute names (`name`, `ca_certificate`, `endpoint`) — not `cluster_name` / `cluster_ca_certificate` / `cluster_endpoint`.

### 2. Register with ArgoCD

ArgoCD manages workloads on the cluster from [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps); it discovers clusters via Secrets stored in [`argocd/config`](https://gitlab.com/gitlab-com/gl-infra/argocd/config).

Follow [How to onboard a GKE cluster into ArgoCD via Terraform](../argocd/README.md#how-to-onboard-a-gke-cluster-into-argocd-via-terraform). Add a `gke-argocd-bootstrap` module block that consumes the cluster's outputs:

```hcl
module "gke-<name>-argocd-bootstrap" {
  source  = "gitlab.com/gitlab-com/gke-argocd-bootstrap/google"
  version = "1.5.0"

  environment = var.environment
  stage       = "non-prod"  # or "prod"

  cluster = {
    name           = module.gke-<name>.name
    endpoint       = "https://${nonsensitive(module.gke-<name>.endpoint)}"
    ca_certificate = base64decode(nonsensitive(module.gke-<name>.ca_certificate))
    location       = local.gke_cluster_zone  # or the region for a regional cluster
    project        = var.project
    region         = var.region
  }

  cluster_role_binding = {
    service_account_email = local.argocd_service_account_email
  }

  providers = {
    gitlab     = gitlab.argocd
    kubernetes = kubernetes.gke-<name>
  }
}
```

Notes on the attributes:

- `cluster.name` / `.endpoint` / `.ca_certificate` come from the upstream GKE module — those are its output names. The legacy internal module exports `cluster_name` / `cluster_endpoint` / `cluster_ca_certificate` instead.
- `nonsensitive()` is needed because the upstream module marks `endpoint` and `ca_certificate` as sensitive; the bootstrap module needs plain strings.
- `stage` is `"non-prod"` for staging, pre-prod, and playground clusters and `"prod"` for production clusters — the ArgoCD ApplicationSets filter on it.
- `providers` — the `kubernetes` provider alias must match the one you configured for the new cluster in `providers.tf`.

Atlantis applies this alongside the cluster module. It creates the cluster registration Secret in `argocd/config` with the labels that ArgoCD ApplicationSets use to fan applications out (`gitlab.com/environment`, `gitlab.com/k8s-cluster-name`, `gitlab.com/stage`, and so on).

Once registered, ArgoCD ApplicationSets fan out platform services (Vault, cert-manager, external-dns, Prometheus, and so on) to the new cluster automatically based on those labels.

### 3. Prometheus and dashboards

Rules for the new cluster are added under `mimir-rules/gitlab-<env>/kube/` in this repo. Dashboards under `dashboards/kubernetes/` pick up the cluster automatically once metrics start flowing.

### 4. Deploy the GitLab chart (main-stage clusters only)

For clusters that will host the GitLab application, follow [Bootstrapping new clusters](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com#bootstrapping-new-clusters) in the `k8s-workloads/gitlab-com` README to apply the initial chart release. Non-application clusters (observability, playground, and so on) skip this step.

### 5. Verify

```sh
glsh kube setup
glsh kube use-cluster <name>
kubectl get nodes
kubectl get pods --all-namespaces
```

Confirm ArgoCD is syncing platform services from the [ArgoCD UI](https://argocd.gitlab.net/) filtered on the new cluster.

## Related

- [`config-mgmt` HOWTO](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/HOWTO.md)
- [ArgoCD onboarding docs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/docs)
- [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md) — replacing an existing cluster
- [k8s-cluster-upgrade.md](k8s-cluster-upgrade.md)
- [Dataplane V2 concepts](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2)
