# Snapshot and restore a StatefulSet volume

> [!warning]
> This procedure has only been tested in staging. Do not run it in production without validating each step against your workload first.

Snapshotting a StatefulSet's persistent volume is useful for:

- Preparing a rollback point before a risky upgrade.
- Ad-hoc backup and restore of stateful workloads (Redis, Postgres, Prometheus).

The modern Kubernetes-native path is [Volume Snapshots (CSI)](https://kubernetes.io/docs/concepts/storage/volume-snapshots/) via a `VolumeSnapshotClass`. GKE supports it through the [Compute Engine Persistent Disk CSI driver](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes#pd_csi_driver_features). Prefer that where available.

The procedure below uses raw GCE disk snapshots and manual PV replacement, which is what we have used historically in staging.

## Prerequisites

- Cluster access — see [k8s-oncall-setup.md](k8s-oncall-setup.md).
- `gcloud` configured for the target project.
- Understanding of what state the StatefulSet's PVs hold and whether losing a replica is safe.

## Procedure

Set variables:

```sh
NS=mimir
STS=mimir-compactor
PROJECT=gitlab-staging-1
```

### 1. Snapshot all volumes

```sh
# List all PVCs for the StatefulSet's pods
kubectl -n "$NS" get pods -l "app.kubernetes.io/name=$STS" -o jsonpath='{.items[*].spec.volumes[*].persistentVolumeClaim.claimName}'

# For each PVC, find the underlying PD name and snapshot it
for pvc in <list>; do
  pv=$(kubectl -n "$NS" get pvc "$pvc" -o jsonpath='{.spec.volumeName}')
  disk=$(kubectl get pv "$pv" -o jsonpath='{.spec.csi.volumeHandle}' | awk -F/ '{print $NF}')
  gcloud --project "$PROJECT" compute disks snapshot "$disk" \
    --snapshot-names "$pvc-$(date +%Y%m%d%H%M%S)" \
    --zone "$(kubectl get pv "$pv" -o jsonpath='{.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[?(@.key=="topology.gke.io/zone")].values[0]}')"
done
```

### 2. Dump manifests

Save copies of the StatefulSet, its PVCs, and its PVs so you can recreate them if needed:

```sh
kubectl -n "$NS" get statefulset "$STS" -o yaml > "/tmp/$STS-sts.yaml"
kubectl -n "$NS" get pvc -l "app.kubernetes.io/name=$STS" -o yaml > "/tmp/$STS-pvcs.yaml"
kubectl get pv -o yaml > /tmp/all-pvs.yaml   # filter after
```

## Restore a single replica

Restoring a single replica from its snapshot requires taking the StatefulSet controller out of the loop temporarily.

1. Orphan-delete the StatefulSet so pods and PVCs stay running:

    ```sh
    kubectl -n "$NS" delete statefulset "$STS" --cascade=orphan
    ```

2. Delete the target pod:

    ```sh
    kubectl -n "$NS" delete pod "$STS-0"
    ```

3. Delete its PVC — this triggers deletion of the PV (backed by the disk in GCE):

    ```sh
    kubectl -n "$NS" delete pvc "data-$STS-0"
    ```

4. Create a new disk from the snapshot with the **same name as the deleted disk**:

    ```sh
    gcloud --project "$PROJECT" compute disks create <disk-name> \
      --source-snapshot <snapshot-name> \
      --zone <zone>
    ```

5. Create a PV pointing to the new disk (adapt from `/tmp/all-pvs.yaml`). Do not create the pod or PVC yet.
6. Recreate the StatefulSet from the manifest:

    ```sh
    kubectl -n "$NS" apply -f "/tmp/$STS-sts.yaml"
    ```

    The controller creates the pod and PVC; the PVC binds to the pre-created PV.

7. Verify the pod comes up healthy and the workload sees the restored data.

## Cleanup

- Delete snapshots you no longer need:

    ```sh
    gcloud --project "$PROJECT" compute snapshots delete <snapshot-name>
    ```

- Confirm no orphaned PVs remain in `Released` state.

## Related

- [Kubernetes Volume Snapshots](https://kubernetes.io/docs/concepts/storage/volume-snapshots/) — CSI-native alternative.
- [GKE: Use a persistent disk with multiple readers](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/preexisting-pd) — attaching a pre-existing PD to a StatefulSet.
- [k8s-sts-guidelines.md](k8s-sts-guidelines.md) — when to use a StatefulSet.
- [k8s-pvc-resize.md](k8s-pvc-resize.md) — grow PVCs online.
