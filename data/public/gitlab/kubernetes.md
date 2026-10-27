# Kubernetes on GitLab.com

GitLab.com runs on Google Kubernetes Engine (GKE). This document is the entry point for the Kubernetes runbooks — for setup and access, start with [Kubernetes on-call setup](k8s-oncall-setup.md).

## Where things live

| Repository | Purpose |
| --- | --- |
| [`config-mgmt`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/) | Terraform for clusters, node pools, subnets, IAM, DNS. Applied via [Atlantis](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/README.md#atlantis). |
| [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps) | Platform workloads managed by [ArgoCD](https://argocd.gitlab.net/): Vault, Prometheus, Mimir, KEDA, cert-manager, external-dns, and everything else previously in `gitlab-helmfiles`. |
| [`argocd/config`](https://gitlab.com/gitlab-com/gl-infra/argocd/config) | Cluster registration Secrets consumed by ArgoCD ApplicationSets. |
| [`k8s-workloads/gitlab-com`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com) | The GitLab application chart. Deployed via `k-ctl`/`helmfile` from CI on `ops.gitlab.net`. |

## Clusters

Each environment runs one regional cluster plus three zonal clusters in `us-east1`.

| Environment | Regional | Zonal |
| --- | --- | --- |
| `gprd` | `gprd-gitlab-gke` | `gprd-us-east1-{b,c,d}` |
| `gstg` | `gstg-gitlab-gke` | `gstg-us-east1-{b,c,d}` |
| `pre` | `pre-gitlab-gke` | — |
| `ops` | `ops-gitlab-gke`, `ops-central` | — |

Regional clusters host Sidekiq (all shards), Mailroom, KAS, Zoekt, and canary web/Shell/Registry in the `gitlab-cny` namespace. Zonal clusters host the main-stage user-facing traffic: web, API, Git, Shell, Registry, Pages, websockets.

Traffic is kept zone-local: each HAProxy node prefers the zonal cluster in its own zone as the active backend, with the other two zones as backup. See [HAProxy](../frontend/haproxy.md) for details.

Regional consolidation is being considered — see [production-engineering#29065](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29065).

### Naming convention

The full name follows `<provider>_<project>_<location>_<cluster_name>`, matching the GKE context format:

- `gke_gitlab-staging-1_us-east1_gstg-gitlab-gke` — regional cluster in `us-east1`
- `gke_gitlab-production_us-east1-b_gprd-us-east1-b` — zonal cluster in `us-east1-b`

DNS records reverse the components to fit hierarchical DNS: `gprd-us-east1-b.us-east1-b.gitlab-production.gke.gitlab.net`.

## Networking

New and rebuilt clusters use [GKE Dataplane V2](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2) (Cilium + eBPF). Older clusters still use Calico and are pending migration under [&1651](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/1651).

Current state (Jul 2026):

- Dataplane V2: `gprd-us-east1-{b,c,d}`, `gstg-us-east1-{b,c,d}`, `pre-gitlab-gke`, `ops-central`
- Calico: `gprd-gitlab-gke`, `gstg-gitlab-gke`, `ops-gitlab-gke`, and other legacy clusters

`NetworkPolicy` resources on Dataplane V2 clusters cannot use CIDR selectors — Cilium enforces via eBPF, not iptables. Use pod selectors instead.

## Common tasks

| Task | Runbook |
| --- | --- |
| First-time access setup | [k8s-oncall-setup.md](k8s-oncall-setup.md) |
| Emergency ConfigMap edit, rolling restart, manual scale | [k8s-operations.md](k8s-operations.md) |
| Add a pod IP range without rebuild | [k8s-operations.md](k8s-operations.md#add-a-secondary-pod-ip-range) |
| Resize a Persistent Volume Claim | [k8s-pvc-resize.md](k8s-pvc-resize.md) |
| Isolate a pod for troubleshooting | [k8s-isolate-pod.md](k8s-isolate-pod.md) |
| Recover a stuck Helm release | [helm-upgrade-stuck.md](helm-upgrade-stuck.md) |
| Ad-hoc CPU profiling, packet capture, `perf` on a node | [k8s-adhoc-observability.md](k8s-adhoc-observability.md) |
| Upgrade a cluster to a new Kubernetes minor | [k8s-cluster-upgrade.md](k8s-cluster-upgrade.md) |
| Rotate cluster CA credentials | [kube-administration.md](kube-administration.md) |
| Provision a new cluster | [k8s-new-cluster.md](k8s-new-cluster.md) |
| Rebuild an existing cluster | [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md) |

## Logs and events

Cluster events land in Cloud Logging. See [Kubernetes engine audit logging](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/audit-logging) for the log names and payload structure.

### Kubernetes object events

Kubernetes emits events for pod scheduling, ReplicaSet creation, image pulls, and so on — the same data `kubectl describe` shows. Cloud Logging stores them under `projects/<project>/logs/events`.

Useful filters:

- All events for a cluster: `logName="projects/<project>/logs/events"`
- Namespace: `jsonPayload.involvedObject.namespace="<ns>"`
- Object kind: `jsonPayload.involvedObject.kind="Pod"` (`Service`, `DaemonSet`, `ReplicaSet`, etc.)
- Object name (supports wildcards):
  - specific pod: `gitlab-registry-68cbc8c489-nh9s9`
  - all pods of a ReplicaSet: `gitlab-registry-68cbc8c489`
  - all pods of a Deployment: `gitlab-registry`

Message content is in `jsonPayload.message`.

### Container logs

Each container's stdout and stderr is captured under `projects/<project>/logs/<container_name>`:

```text
logName="projects/gitlab-pre/logs/registry"
```

Filter one stream with `labels."container.googleapis.com/stream"` (values: `stdout`, `stderr`). Message content is in `textPayload`.

### Cluster-level events

- Deployment patches (image bumps): `protoPayload.methodName="io.k8s.apps.v1.deployments.patch"`
- ReplicaSet creation: `protoPayload.methodName="io.k8s.apps.v1.replicasets.create"`
- Node preemption (Spot VMs): `jsonPayload.event_subtype="compute.instances.preempted"` — note that we run some pools as Spot VMs; nodes disappear without warning and their in-flight metrics stop.

Grafana log links per service are wired into the metrics catalog and surfaced from alerts.

## Alerts

Alert playbooks live under [`alerts/`](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/kube/alerts):

- [`KubeSchedulingFailures`](alerts/KubeSchedulingFailures.md) — pods stuck `Unschedulable` (`KubePodsUnschedulable`, `KubeDaemonSetPodsUnschedulable`) and Cluster Autoscaler scale-up failures (`KubeServiceClusterScaleupsErrorSLOViolation`).
- [`KubeContainersWaitingInError`](alerts/KubeContainersWaitingInError.md) — more than 50% of a Deployment's containers are stuck waiting to start for a non-`ContainerCreating` reason.
- [`KubernetesClusterZombieProcesses`](alerts/KubernetesClusterZombieProcesses.md) — a workload is leaking defunct child processes; risks PID and file handle exhaustion.
- [`GitLabZonalComponentVersionsOutOfSync`](alerts/GitLabZonalComponentVersionsOutOfSync.md) — GitLab components on zonal clusters have drifted to different versions past the normal deploy window.
- [`HPAScaleCapability`](alerts/HPAScaleCapability.md) — a Horizontal Pod Autoscaler is at `maxReplicas` (`component_saturation_slo_out_of_bounds:kube_horizontalpodautoscaler_desired_replicas`).
- [`GKENodeCountCritical`](alerts/GKENodeCountCritical.md) — a GKE node pool has reached its Terraform-defined maximum (`component_saturation_slo_out_of_bounds:kube_pool_max_nodes` hard SLO). The soft threshold (90%) is documented in the same playbook.
- [`kube_persistent_volume_claim_disk_space`](alerts/kube_persistent_volume_claim_disk_space.md) — a PVC is running out of disk space.

Other `component_saturation_slo_out_of_bounds:kube_*` alerts (node IPs, container throttling, container CPU/memory limits, PVC inodes, pool CPU) are auto-generated from [`metrics-catalog/services/kube.jsonnet`](../../metrics-catalog/services/kube.jsonnet) and do not have dedicated playbooks yet.

## Related documentation

- [ArgoCD](../argocd/README.md) — GitOps for platform workloads
- [`config-mgmt` HOWTO](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/HOWTO.md) — Terraform operations
- [HAProxy](../frontend/haproxy.md) — zonal traffic routing
- [Vault administration](../vault/kube-administration.md) — Kubernetes auth backend
