# Runbook: Istio 503 Service Unavailable & UC / UF Response Flags

## Severity: Critical (P1)
## Service: Istio Service Mesh / Envoy Data Plane
## Last Updated: 2026-10-18

### 1. Overview
In an Istio service mesh, HTTP 503 errors typically originate from the Envoy sidecar proxy rather than the upstream application. Envoy attaches response flags to its access logs that pinpoint the exact failure reason:
- `UF` = Upstream Connection Failure
- `UC` = Upstream Connection Termination
- `UO` = Upstream Overflow (circuit breaker tripped)
- `NR` = No Route configured

### 2. Immediate Triage Commands
```bash
# Check Envoy access logs for response flags
kubectl logs <client-pod> -c istio-proxy -n <namespace> | grep -E '503|UF|UC|UO|NR'

# Check Istio proxy synchronization status
istioctl proxy-status

# Dump active clusters and endpoints for target service
istioctl proxy-config endpoints <client-pod>.<namespace> --cluster "outbound|8080||target-service.namespace.svc.cluster.local"
```

### 3. Root Cause Analysis

#### Flag: "UF" or "UC" with 503
- **Cause 1: Missing or mismatched DestinationRule mTLS mode.**
  - If the target service namespace has `PeerAuthentication` set to `STRICT`, but the client is sending plain HTTP because no `DestinationRule` with `ISTIO_MUTUAL` exists.
  - **Fix:** Ensure matching `DestinationRule`:
    ```yaml
    apiVersion: networking.istio.io/v1beta1
    kind: DestinationRule
    metadata:
      name: default-mtls
      namespace: default
    spec:
      host: "*.default.svc.cluster.local"
      trafficPolicy:
        tls:
          mode: ISTIO_MUTUAL
    ```
- **Cause 2: Target pod is not ready or failing readiness checks.**
  - Envoy will not route traffic to endpoints that Kubernetes marks as unready.
  - **Fix:** Check `kubectl get endpoints <service-name> -n <namespace>`. If empty, inspect pod readiness probes.

#### Flag: "UO" with 503 (Circuit Breaking)
- **Cause:** Upstream connection pool or max pending requests limit in `DestinationRule` exceeded.
- **Fix:** Tune `maxConnections` and `maxPendingRequests` in the `DestinationRule.spec.trafficPolicy.connectionPool`.

### 4. Verification
Verify that traffic returns HTTP 200:
```bash
kubectl exec -it <client-pod> -c istio-proxy -n <namespace> -- curl -I http://target-service:8080/health
```
