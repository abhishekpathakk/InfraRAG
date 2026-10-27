# Kubernetes operations

Task-oriented reference for common Kubernetes operations on GitLab.com. For access setup, see [k8s-oncall-setup.md](k8s-oncall-setup.md).

## Upgrade the GitLab application

Most components are rolled out by Auto-Deploy:

- Chart version bumps follow [Setting Chart Version](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com#setting-chart-version) in the `k8s-workloads/gitlab-com` README.
- Auto-Deploy semantics, exceptions, and configuration-change flows are documented in [`DEPLOYMENT.md`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/DEPLOYMENT.md#auto-deploy).

## Manually scale a Deployment

Emergency use: when we need to pin replicas to a specific number outside the HPA loop.

```sh
kubectl -n gitlab scale deployments/gitlab-sidekiq-memory-bound-v1 --replicas=0
```

The HPA re-takes control on its next reconcile if `minReplicas ≥ 1`. Scaling to `0` disables HPA autoscaling for that workload until at least one replica exists again:

```sh
kubectl -n gitlab scale deployments/gitlab-sidekiq-memory-bound-v1 --replicas=1
```

Inspect HPA state:

```sh
kubectl get hpa -n gitlab
# NAME              REFERENCE                    TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
# gitlab-registry   Deployment/gitlab-registry   47%/75%   2         100       21         11d
```

Most workloads scale on CPU utilisation. HPA cap saturation surfaces as the [`HPAScaleCapability`](alerts/HPAScaleCapability.md) alert. Workload memory quotas are visible on the [Kubernetes compute resources dashboard](https://dashboards.gitlab.net/d/kubernetes-resources-workload/kubernetes-compute-resources-workload).

See [Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/).

## Rolling restart

For feature flags that require app restart, or when kicking a workload to pick up a ConfigMap change:

```sh
kubectl -n gitlab rollout restart deployment/gitlab-gitlab-shell
kubectl -n gitlab rollout status  deployment/gitlab-gitlab-shell
```

## Emergency ConfigMap edit

During an incident you may need to change a single key in a ConfigMap before the change can land in the config repo and roll out through the deploy pipeline.

`glsh kube configmap` handles this with a backup, a diff, and a confirmation prompt. Select the cluster first with `glsh kube use-cluster <cluster>`.

```sh
# Show the current value of one key
glsh kube configmap get gitlab-gitlab-shell -n gitlab -k config.yml.tpl

# Edit it in $EDITOR, review the diff, then confirm
glsh kube configmap edit gitlab-gitlab-shell -n gitlab -k config.yml.tpl

# Or feed a prepared value in
glsh kube configmap edit gitlab-gitlab-shell -n gitlab -k config.yml.tpl < config.yml.tpl
```

A JSON backup of the ConfigMap is written to your temp dir before anything is applied. Revert with `kubectl apply -f <backup>`.

This is a temporary override. The deploy tooling overwrites the ConfigMap with what is in [k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com) on the next deploy, so open an MR there to make the change permanent. Pods pick up the new value on restart; initiate a rolling restart after the edit.

## Deployment lifecycle

Kubernetes keeps ReplicaSets for a limited number of Deployment revisions. Kubernetes emits events for pod create/delete, but not for ReplicaSet or Deployment changes. The most complete source is the [GKE audit log](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/audit-logging) — go to Logs Explorer in the relevant GCP project.

### Diff between deployment revisions

```sh
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell --revision 22 > /tmp/rev22
kubectl -n gitlab rollout history deployment/gitlab-gitlab-shell --revision 21 > /tmp/rev21
diff -u /tmp/rev21 /tmp/rev22
```

You can also find the patch body in the audit log:

```text
protoPayload.methodName="io.k8s.apps.v1.deployments.patch"
```

### Timestamp of a change

Audit log filters:

- Deployment patch (image update): `protoPayload.methodName="io.k8s.apps.v1.deployments.patch"`
- ReplicaSet creation: `protoPayload.methodName="io.k8s.apps.v1.replicasets.create"`

For pipeline-driven changes, look at the corresponding pipeline in `k8s-workloads/gitlab-com`, `argocd/apps`, or `config-mgmt`.

## Create a new node pool

Node pool changes go through Atlantis in `config-mgmt`.

1. Open an MR adding the new node pool to the environment's `gke-regional.tf` or `gke-zonal.tf` (or to the `gke_zonal_node_pools` / `gke_regional_node_pools` local for our modules). See [`environments/gprd/gke-zonal.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/gke-zonal.tf) and [`environments/gprd/gke-regional.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/gke-regional.tf) for the shape.
2. `atlantis plan -p <env>` in the MR.
3. `atlantis apply -p <env>` once approved. Atlantis merges on success.
4. If replacing an existing pool: cordon and drain the old pool first (see below), then remove it in a follow-up MR.

### Cordon and drain

```sh
OLD_POOL=<name>

# Cordon
for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool="$OLD_POOL" -o=name); do
  kubectl cordon "$node"
  read -r -p "Node $node cordoned, enter to continue ..."
done

# Drain (--delete-emptydir-data replaces the deprecated --delete-local-data)
for node in $(kubectl get nodes -l cloud.google.com/gke-nodepool="$OLD_POOL" -o=name); do
  kubectl drain --force --ignore-daemonsets --delete-emptydir-data --grace-period=10 "$node"
  read -r -p "Node $node drained, enter to continue ..."
done
```

See [Safely drain a node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/).

## Add a secondary pod IP range

When a cluster's pod subnet is running out of IPs and a full rebuild is not warranted, GKE supports adding secondary pod CIDR ranges to a live cluster. Docs: [Multi-pod CIDR](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/multi-pod-cidr).

The change is low risk: the existing range and running nodes are unaffected. If the new range is misconfigured, new nodes trying to use it fail to become healthy — no impact on running workloads.

Example CR: [production#21390](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21390). Example MR shape: [config-mgmt!13329](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/13329).

Steps:

1. Reserve the new secondary range in Terraform (subnet secondary range block).
2. Add it to the cluster module's `additional_pod_ip_cidr_ranges`.
3. `atlantis plan -p <env>` → review → `atlantis apply -p <env>`.
4. Watch `component_saturation_slo_out_of_bounds:kube_pool_max_nodes` and the [kube overview dashboard](https://dashboards.gitlab.net/d/kube-main/kube-overview) — the effective node cap should rise.

## Attach to a running container

> [!caution]
> Production containers can be servicing customer traffic. Debugging can incur performance penalties or expose Red-classified data. Remove any pod that you have modified when done.

### Find the container

```sh
kubectl get pods -n gitlab -o wide  # get the node name
kubectl get pod "$POD" -n gitlab -o json | jq .status.containerStatuses
```

Note the full `containerID` (long hash form); some `runc` operations need it.

### SSH into the node and exec

```sh
gcloud compute ssh --tunnel-through-iap "$NODE" \
  --zone "$(gcloud compute instances list --filter name="$NODE" --format='value(zone)')" \
  --project gitlab-production

crictl ps | grep "$POD"
crictl exec -it "$CONTAINER_ID" /bin/bash   # or /bin/sh if bash is missing
```

### Higher privileges via `runc`

If the container image lacks tools or you need root:

```sh
runc --root /run/containerd/runc/k8s.io/ \
  exec -t -u 0 "$FULL_CONTAINER_ID" /bin/bash
```

`crictl` cannot open a new PID namespace as root; `runc` can. Use the full container ID.

### Ephemeral debug container

For images without a shell, [ephemeral containers](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/#ephemeral-container) attach to the pod without recreating it. GA since Kubernetes 1.25.

```sh
kubectl debug -it mypod --image=busybox --target=mypod
```

Combined with [process namespace sharing](https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/), the debug container can see other processes in the pod.

### Run a command in the pod's network namespace

Useful when you want `tcpdump`, `ss`, or `curl` scoped to a single pod without adding a sidecar. The network namespace is shared by every container in the pod, so any container's PID works.

```sh
crictl ps -a                                     # get container ID
CONTAINER_PID=$( crictl inspect <container-id> | jq -r .info.pid )

# Prefer toolbox — it has strace, tcpdump, etc.
toolbox --network-namespace-path=/proc/$CONTAINER_PID/ns/net

# Or nsenter on the host, if toolbox is not usable.
nsenter --target $CONTAINER_PID --mount --uts --ipc --net --pid
```

### Attach a PVC to toolbox

Read (or write, with care) a pod's persistent volume from toolbox without touching the pod:

```sh
toolbox --bind=/var/lib/kubelet/pods/<pod-uid>/volume-subpaths/<pvc-id>/...
# read-only variant:
toolbox --bind-ro=/var/lib/kubelet/pods/<pod-uid>/volume-subpaths/<pvc-id>/...
```

Find `<pod-uid>` from `kubectl get pod <pod> -o jsonpath='{.metadata.uid}'` and `<pvc-id>` from `ls /var/lib/kubelet/pods/<pod-uid>/volume-subpaths/`.

### Toolbox on the node

GKE COS nodes ship [toolbox](https://docs.cloud.google.com/container-optimized-os/docs/how-to/toolbox), a container with the host filesystem mounted at `/media/root/`:

```sh
toolbox                              # interactive session
toolbox apt install -y strace
toolbox apt install -y tcpdump jq
```

Only one toolbox session runs on a host at a time. See [k8s-adhoc-observability.md](k8s-adhoc-observability.md) for profiling and packet-capture recipes.

## Related

- [Ad hoc observability on GKE nodes](k8s-adhoc-observability.md) — CPU profiling, `perf`, `tcpdump`, `pidstat`.
- [Upgrade a cluster](k8s-cluster-upgrade.md) — control-plane and node-pool version bumps.
- [Rebuild a cluster](k8s-cluster-rebuild.md) — full cluster replacement, including HAProxy drain.
- [Kubernetes overview](kubernetes.md) — cluster inventory and repository map.
