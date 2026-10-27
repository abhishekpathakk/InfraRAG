# Kubernetes Runbook: NodeDiskPressure & Eviction Triage

## Overview & Symptoms
`NodeDiskPressure` occurs when the Kubelet detects that available disk space or inodes on the root filesystem (or the image filesystem) falls below configured eviction thresholds (default: available disk < 15% or free inodes < 5%). When triggered:
1. The node status updates to `DiskPressure=True`.
2. The Kubelet immediately refuses to schedule new pods on the affected node.
3. The Kubelet begins evicting active non-critical (BestEffort, then Burstable) pods to prevent kernel panic.
4. Pods enter `Evicted` status with the reason `The node was low on resource: ephemeral-storage`.

## Immediate Diagnostic Checklist

### 1. Identify Affected Nodes
```bash
kubectl get nodes -o wide
kubectl describe node <node-name> | grep -A 8 -i "Conditions"
```
Look for:
```text
DiskPressure    True    KubeletHasDiskPressure
```

### 2. Inspect Node Storage Utilization via SSH or Debug Pod
```bash
kubectl debug node/<node-name> -it --image=busybox -- df -h
```
Check disk utilization on `/var/lib/kubelet`, `/var/lib/containerd`, and `/var/log`.

### 3. List Top Ephemeral Storage Consuming Pods
```bash
kubectl get pods -A --sort-by='.status.ephemeralStorage' -o wide
kubectl describe pod <evicted-pod-name> -n <namespace> | grep -i -A 5 "Status"
```

## Root Causes & Triage Paths

### Scenario A: Unrotated Container Logs on the Host
Applications writing excessive stdout/stderr logs can exhaust `/var/log/pods/` if Kubelet log rotation is not configured properly.
- **Immediate Fix:**
```bash
# Check log directory size on node
du -sh /var/log/pods/* | sort -hr | head -n 10
# Clean up older rotated logs
find /var/log/pods -name "*.gz" -delete
```

### Scenario B: Accumulated Dangling Container Images
Container runtime (`containerd` or `crio`) failed to prune unreferenced layers.
- **Immediate Fix:**
```bash
# Force garbage collection via crictl
crictl rmi --prune
```

### Scenario C: Pod Writing Large Ephemeral Data Without Limits
A pod writing temporary data directly to its local container layer or `emptyDir` volume rather than a PVC.
- **Immediate Fix:** Evict or scale down the rogue workload:
```bash
kubectl scale deployment <rogue-deployment> -n <namespace> --replicas=0
```

## Permanent Resolution & Best Practices
1. **Define Ephemeral-Storage Resource Quotas:**
```yaml
resources:
  limits:
    ephemeral-storage: "2Gi"
  requests:
    ephemeral-storage: "500Mi"
```
2. **Configure Kubelet Eviction Thresholds in `kubelet-config.yaml`:**
```yaml
evictionHard:
  nodefs.available: "10%"
  nodefs.inodesFree: "5%"
  imagefs.available: "15%"
```
3. **Automate Root Volume Autoscaling:** Attach EBS volume auto-expansion using AWS EBS CSI Driver or Karpenter automated node replacement.
