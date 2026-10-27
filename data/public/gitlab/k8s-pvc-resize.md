# Resize a PersistentVolumeClaim

Kubernetes supports online expansion of PVCs backed by XFS, ext3, or ext4. Editing the PVC's requested storage triggers the storage backend to grow the underlying disk, and the file system is expanded in place with no pod restart if the CSI driver supports it. See [Expanding Persistent Volumes Claims](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#expanding-persistent-volumes-claims).

PVCs can only grow — the Kubernetes API rejects shrinks.

## Deployment PVCs

Example: resize a PVC used by a Deployment from 10 GiB to 20 GiB.

### 1. Preflight

- Confirm the storage class supports expansion:

    ```sh
    kubectl get storageclass -o custom-columns=NAME:.metadata.name,EXPAND:.allowVolumeExpansion
    ```

- Prepare the size change in Helm / ArgoCD / whatever manages the PVC (do not merge yet).
- Have cluster access — see [k8s-oncall-setup.md](k8s-oncall-setup.md).

### 2. Confirm the current state

```sh
kubectl -n thanos describe Deployment/receive-gitlab-thanos-compactor
kubectl -n thanos get pvc receive-gitlab-thanos-compactor
```

### 3. Apply the change

Merge your Helm / ArgoCD MR. The controller patches the PVC's `spec.resources.requests.storage`, the backend grows the disk, and the file system expands online.

Verify:

```sh
kubectl -n thanos get pvc -l app.kubernetes.io/component=compactor -o wide
```

## StatefulSet PVCs (data-only change)

StatefulSet controllers do not propagate storage changes from `volumeClaimTemplates` to existing PVCs — see [Kubernetes enhancement #661](https://github.com/kubernetes/enhancements/issues/661) (closed, no KEP merged). To grow only the PVC data without touching the template, patch each PVC directly.

The GCE PD CSI driver used by GKE supports [online volume expansion](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-expansion), so no pod bounce is required — the file system grows in place while the pod continues running.

1. Find the PVCs:

    ```sh
    kubectl -n mimir get pvc | grep compact
    ```

2. Patch each PVC's `spec.resources.requests.storage` to the new value:

    ```sh
    kubectl -n mimir patch pvc <pvc-name> -p '{"spec":{"resources":{"requests":{"storage":"50Gi"}}}}'
    ```

3. Confirm the resize completed:

    ```sh
    kubectl -n mimir get pvc | grep compact
    ```

    Rarely, if the CSI driver cannot grow the volume online, the PVC gains a `FileSystemResizePending` condition and completes on the next pod restart:

    ```yaml
    - message: Waiting for user to (re-)start a pod to finish file system resize of volume on node.
      status: "True"
      type: FileSystemResizePending
    ```

    Bounce the pod to unblock it — for a StatefulSet, scale to 0 and back:

    ```sh
    kubectl -n mimir scale statefulsets/mimir-compactor --replicas=0
    kubectl -n mimir scale statefulsets/mimir-compactor --replicas=1
    ```

## StatefulSet PVCs (template change)

Kubernetes forbids mutating a StatefulSet's `volumeClaimTemplates`. Attempting to sync an ArgoCD change that modifies it is rejected as long as the StatefulSet exists. The safe path is **orphan-delete**: remove the StatefulSet controller but leave pods and PVCs running.

### 1. Prepare the change

Open the ArgoCD / Helm MR with the new `volumeClaimTemplates` size. Do not merge yet.

### 2. Orphan-delete the StatefulSet

```sh
kubectl delete statefulset <sts> -n <namespace> --cascade=orphan
```

Repeat per StatefulSet if the workload uses one StatefulSet per zone.

Pods and PVCs keep running.

### 3. Resize the PVCs

```sh
NAMESPACE=<namespace>
SIZE=<new-size>            # e.g. 250Gi
SELECTOR=<label-selector>  # from the StatefulSet's spec.selector.matchLabels

for pvc in $(kubectl get pvc -n "$NAMESPACE" -l "$SELECTOR" -o jsonpath='{.items[*].metadata.name}'); do
  kubectl patch pvc "$pvc" -n "$NAMESPACE" -p "{\"spec\":{\"resources\":{\"requests\":{\"storage\":\"$SIZE\"}}}}"
done
```

To find the right selector:

```sh
kubectl get statefulset <sts> -n <namespace> -o jsonpath='{.spec.selector.matchLabels}'
```

### 4. Merge the MR

ArgoCD recreates the StatefulSet with the updated `volumeClaimTemplates`; pods reschedule against the already-resized PVCs.

### 5. Verify

```sh
kubectl get statefulset <sts> -n <namespace>
kubectl get pods         -n <namespace> -l "$SELECTOR"
kubectl get pvc          -n <namespace> -l "$SELECTOR"
```

## Rollback

PVCs cannot be shrunk. If you have orphan-deleted the StatefulSet but not yet merged the config MR, recreate the StatefulSet manually at the original size to restore the controller. The PVC resize itself is irreversible.

## Related

- [Kubernetes: Expanding Persistent Volumes Claims](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#expanding-persistent-volumes-claims)
- [GKE Storage Classes](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes#storageclasses)
- [k8s-operations.md](k8s-operations.md) — general workload operations.
- [alerts/kube_persistent_volume_claim_disk_space.md](alerts/kube_persistent_volume_claim_disk_space.md) — PVC saturation alert.
