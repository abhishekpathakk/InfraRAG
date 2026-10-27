# Kubernetes Ingress Runbook: HTTP 504 Gateway Timeout Triage

## Overview & Symptoms
HTTP 504 Gateway Timeout occurs when an edge proxy or Kubernetes Ingress Controller (Nginx Ingress, AWS Load Balancer Controller / ALB, Traefik) fails to receive a timely response from an upstream backend service pod within the configured timeout window.
- **Client sees:** `504 Gateway Time-out`
- **Ingress Controller log shows:** `upstream timed out (110: Connection timed out) while reading response header from upstream`
- **Impact:** Failed API transactions, degraded user checkout/request flows, and customer-facing incident alerts.

## Immediate Diagnostic Checklist

### 1. Inspect Ingress Controller Access Logs
```bash
kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100 | grep " 504 "
```
Look for:
```text
[error] upstream timed out (110: Connection timed out) while reading response header from upstream, client: 10.0.1.20, server: api.company.com, upstream: "http://10.244.2.14:8080/checkout"
```

### 2. Verify Upstream Pod Endpoints & Health
```bash
# Check if the service has active, ready endpoints
kubectl get endpoints <service-name> -n <namespace>
# Check if upstream pods are CPU throttled or deadlocked
kubectl top pods -n <namespace> -l app=<app-name>
```

### 3. Trace Backend Pod Thread Dumps / High Latency
```bash
kubectl logs -n <namespace> -l app=<app-name> --tail=200 | grep -E "(timeout|deadlock|OutOfMemory)"
```

## Root Causes & Triage Paths

### Scenario A: Backend Processing Exceeds Ingress Timeout Window
Heavy database queries, slow external API calls, or garbage collection pauses exceed the default 60-second Nginx `proxy-read-timeout`.
- **Immediate Fix:** Add timeout annotations to the Ingress resource:
```yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "15"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "180"
```
For AWS ALB Ingress:
```yaml
metadata:
  annotations:
    alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=180
```

### Scenario B: Upstream Pod Crashing or Terminating During In-Flight Requests
Pods terminating due to deployment rollouts without proper pre-stop lifecycle hooks and connection draining.
- **Immediate Fix:** Add `preStop` hook to delay pod shutdown until Ingress drops the IP from the routing table:
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
```

### Scenario C: Backend Thread Pool Saturation / Database Lock
Upstream pods are reachable via TCP, but all HTTP worker threads are blocked waiting on database connections or locks.
- **Immediate Diagnostic:**
```bash
kubectl exec -it <pod-name> -n <namespace> -- netstat -an | grep 8080 | wc -l
```
Scale out the backend deployment to distribute the concurrent request queue:
```bash
kubectl scale deployment <app-deployment> -n <namespace> --replicas=<current_replicas + 3>
```

## Prevention & SRE Guardrails
1. Implement circuit breakers and client-side timeouts in the application code.
2. Configure Horizontal Pod Autoscaler (HPA) targeting CPU utilization < 70% or custom HTTP request latency metrics.
3. Configure readiness probe failure thresholds to pull unhealthy pods before client requests fail with 504.
