# Runbook: Kubernetes CrashLoopBackOff Troubleshooting

## Severity: High (P2)
## Service: Kubernetes Cluster Workloads
## Last Updated: 2026-10-15

### 1. Overview
A `CrashLoopBackOff` status indicates that a Kubernetes pod has repeatedly crashed, and the kubelet is waiting with an exponential backoff delay before restarting it again (up to a 5-minute cap).

### 2. Immediate Triage Commands
Run the following commands to inspect the failing pod:
```bash
# Check pod status and restart count
kubectl get pods -n <namespace> -l app=<app-label>

# Inspect pod termination reason and exit code
kubectl describe pod <pod-name> -n <namespace>

# Check current container logs
kubectl logs <pod-name> -n <namespace>

# Check logs of previous crashed container instance (CRITICAL)
kubectl logs <pod-name> -n <namespace> --previous
```

### 3. Common Root Causes & Remediation

#### Exit Code 1 / General Application Error
- **Cause:** Application threw an unhandled exception, syntax error, or missing runtime dependency.
- **Remediation:** Inspect `kubectl logs <pod-name> --previous`. Verify entrypoint scripts and application config files.

#### Exit Code 137 (OOMKilled)
- **Cause:** Container consumed more memory than its configured `resources.limits.memory`. The Linux kernel Out-Of-Memory killer invoked `SIGKILL`.
- **Remediation:** Refer to the `Kubernetes OOMKilled Runbook`. Increase memory limits or profile memory leaks in the JVM/Go heap.

#### Exit Code 139 (Segmentation Fault)
- **Cause:** Memory access violation in compiled binary or native C/C++ binding.
- **Remediation:** Check architecture compatibility (e.g., amd64 vs arm64) and native shared library versions (`glibc` vs `musl`).

#### Misconfigured Liveness Probe
- **Cause:** The liveness probe timeout is too short, or initial delay is insufficient for cold starts.
- **Remediation:** Check `describe pod` for `Liveness probe failed: HTTP probe failed with statuscode: 500`. Increase `initialDelaySeconds` and `periodSeconds`.

### 4. Verification & Resolution
After applying patches to the Deployment:
```bash
kubectl rollout status deployment/<deployment-name> -n <namespace>
```
Verify that container status changes from `CrashLoopBackOff` to `Running` and readiness probe succeeds (1/1 Ready).
