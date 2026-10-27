# Runbook: Istio mTLS Strict Mode Connection Failures

## Severity: High (P2)
## Service: Istio Security & Mutual TLS (mTLS)
## Last Updated: 2026-10-22

### 1. Overview
When an Istio namespace or workload is configured with `PeerAuthentication` in `STRICT` mode, any client connecting over plain unencrypted TCP/HTTP without an authenticated mTLS certificate handshake will be immediately rejected with TCP connection reset or `connection termination`.

### 2. Immediate Triage Commands
```bash
# Check PeerAuthentication policy in the target namespace
kubectl get peerauthentication -n <target-namespace> -o yaml

# Inspect client Envoy sidecar TLS certificates
istioctl proxy-config secret <client-pod>.<namespace>

# Test connection with and without mTLS
kubectl exec -it <client-pod> -c istio-proxy -n <namespace> -- \
  openssl s_client -connect <target-service>.<target-namespace>.svc.cluster.local:8080
```

### 3. Root Cause Analysis

#### Client pod lacks an Istio sidecar (`istio-injection=disabled`)
- **Symptom:** A legacy or third-party pod (e.g. Prometheus scraper, external job) cannot connect to a STRICT mTLS service.
- **Fix:** Either inject the Envoy sidecar into the client pod (`kubectl label namespace <client-ns> istio-injection=enabled`) or configure a `PeerAuthentication` port-level exception:
  ```yaml
  apiVersion: security.istio.io/v1beta1
  kind: PeerAuthentication
  metadata:
    name: allow-metrics-plaintext
    namespace: prod
  spec:
    selector:
      matchLabels:
        app: backend-api
    portLevelMtls:
      9090:
        mode: PERMISSIVE
  ```

#### Missing DestinationRule for cross-namespace or egress traffic
- **Symptom:** Client has a sidecar, but traffic fails because the client does not initiate TLS handshake.
- **Fix:** Apply a cluster-wide or namespace-scoped `DestinationRule` specifying `mode: ISTIO_MUTUAL`.
