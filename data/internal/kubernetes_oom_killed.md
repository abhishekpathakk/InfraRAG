# Runbook: Kubernetes OOMKilled (Exit Code 137)

## Severity: High (P2)
## Service: Kubernetes Node Kubelet & Workloads
## Last Updated: 2026-10-20

### 1. Overview
An `OOMKilled` event indicates that a container or pod exceeded its physical memory limit, or the Kubernetes node ran completely out of allocatable memory. The Linux kernel Out-Of-Memory (cgroup) killer terminates the highest-badness container process with signal 9 (`SIGKILL`, exit code `128 + 9 = 137`).

### 2. Immediate Triage Commands
```bash
# Verify termination reason is OOMKilled
kubectl describe pod <pod-name> -n <namespace> | grep -E "Reason:|Exit Code:"

# Check node memory pressure
kubectl get nodes
kubectl describe node <node-name> | grep -E "MemoryPressure|Allocatable"

# Check pod memory usage metrics
kubectl top pod <pod-name> -n <namespace> --containers
```

### 3. Root Cause Analysis & Mitigation

#### Scenario A: Container Memory Limit Exceeded (Cgroup Limit)
- **Symptom:** `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`. The node itself is healthy (`MemoryPressure: False`).
- **Cause:** The container's working set memory crossed `spec.containers[*].resources.limits.memory`.
- **Fix:**
  1. For JVM applications: set `-XX:MaxRAMPercentage=75.0` or `-Xmx` explicitly.
  2. Increase container limits in Deployment spec:
     ```yaml
     resources:
       requests:
         memory: "1Gi"
       limits:
         memory: "2Gi"
     ```

#### Scenario B: Node-Level Eviction
- **Symptom:** Node condition shows `MemoryPressure: True`. Pods with `BestEffort` or `Burstable` QoS classes are evicted with `The node was low on resource: memory`.
- **Fix:** Configure Kubernetes Horizontal Pod Autoscaler (HPA) or cluster autoscaler to scale out nodes, and always define explicit `requests` and `limits` to guarantee `Guaranteed` QoS for critical workloads.
