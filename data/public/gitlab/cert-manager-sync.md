# Runway cert-manager-sync Failure

## Overview

- **What does this alert mean?** The [cert-manager-sync](https://github.com/robertlestak/cert-manager-sync) service on Runway EKS clusters is not running or not in a ready state. This service is responsible for synchronizing certificate objects managed by cert-manager with AWS ACM (AWS Certificate Manager).
- **What factors can contribute?** Pod crashes, resource constraints, configuration errors, AWS API failures, or deployment issues on the EKS cluster.
- **What parts of the service are affected?** Certificate lifecycle management for workloads running on Runway EKS clusters. If cert-manager-sync is down, certificates will still get auto-renewed by cert-manager, but they will not be synchronized with AWS ACM, which could lead to service outages due to certificate expiration.
- **What action is the recipient expected to take?** Investigate why the pod is down or not ready, check logs for errors, resource constraints, IAM changes related to AWS ACM (pod identity) and restore the service to ensure certificates remain valid.

## Services

- **Service:** cert-manager-sync (part of Runway Infrastructure in EKS clusters)
- **Team:** Runway

## Metrics

- **Metric Explanation:** This alert is based on Kubernetes metrics:
  - `kube_deployment_status_replicas_available`: Number of available replicas for the cert-manager-sync deployment (measured in count)
  - `kube_pod_status_ready`: Pod readiness status (boolean: 0 = not ready, 1 = ready)

- **Threshold Reasoning:** The threshold is set to 0 available replicas or 0 ready pods for 5 minutes. This ensures the service is completely unavailable before alerting, avoiding false positives from brief pod restarts.

- **Expected Behavior:** Under normal conditions, cert-manager-sync should have at least 1 available and ready replica running on each EKS cluster. The metric should consistently show a value > 0.

## Alert Behavior

- **Silencing:** This alert can be silenced during planned maintenance windows for cert-manager-sync updates or EKS cluster upgrades. Use the Alertmanager UI to create silences matching `alertname=~"RunwayCertManagerSync.*"` and the specific cluster labels.

- **Expected Frequency:** This should be a rare alert. If firing frequently, it indicates instability in the cert-manager-sync deployment or underlying infrastructure issues.

## Severities

- **Severity Assignment:** This alert is set to **s3 (high)** because certificate expiration can cause service outages for workloads relying on HTTPS.
  - **Impact:** All workloads on the affected EKS cluster that depend on certificates managed by cert-manager
  - **Scope:** Affects potentially customer-facing services

- **Things to Check:**
  - Is the pod actually down or just not ready?
  - Are there resource constraints (CPU/memory) preventing the pod from starting?
  - Are there any recent changes to the deployment or EKS cluster?
  - Is AWS ACM accessible from the cluster (or possible IAM changes)?

## Verification

- **Prometheus Query:**
  - Down: `kube_deployment_status_replicas_available{deployment="cert-manager-sync",cloud_runtime="eks"} == 0`
  - Not Ready: `kube_pod_status_ready{pod=~"cert-manager-sync.*", condition="true", cloud_runtime="eks"} == 0`

- **Log Queries:**
  - Pod logs: `kubectl logs -n cert-manager-sync deployment/cert-manager-sync`

## Troubleshooting

**Basic Troubleshooting Order:**

1. **Check pod status:**

   ```bash
   kubectl get pods -n cert-manager-sync -l app=cert-manager-sync
   kubectl describe pod <pod-name> -n cert-manager-sync
   ```

2. **Check pod logs:**

   ```bash
   kubectl logs -n cert-manager-sync deployment/cert-manager-sync --tail=100
   ```

3. **Verify AWS ACM connectivity:**
   - Check if the pod has proper IAM permissions to access AWS ACM
   - Verify AWS API endpoints are reachable from the cluster

4. **Check deployment status:**

   ```bash
   kubectl describe deployment cert-manager-sync -n cert-manager-sync
   kubectl rollout status deployment/cert-manager-sync -n cert-manager-sync
   ```

## Possible Resolutions

- **Pod Crash Loop:** Check logs for application errors, verify configuration, ensure AWS credentials are valid
- **Resource Constraints:** Increase pod resource requests/limits or scale down other workloads
- **AWS ACM Connectivity:** Verify IAM role permissions, check security group rules, test AWS API connectivity
- **EKS Cluster Issues:** Check cluster health, node status, and network connectivity

## Escalation

- **When to Escalate:** If the pod remains down after 15 minutes of troubleshooting, or if multiple clusters are affected
- **Escalation Path:**
  1. First: Check #g_runway Slack channel for known issues
  2. Then: Escalate to the Runway team lead

- **Slack Channels:**
  - `#f_runway` - Reach out to the Runway team for support
  - `#s_production_engineering` - Production Engineering team
  - `#ext-aws-support-gitlab` - External channel to collaborate with GitLab's AWS Account and Support team

## Related Links

- [Runway Service Documentation](README.md)
- [cert-manager-sync Documentation](https://github.com/robertlestak/cert-manager-sync/tree/main)
