# AWS Load Balancer Runbook: NLB/ALB Unhealthy Target Host Triage

## Overview & Symptoms
When traffic arrives at an AWS Application Load Balancer (ALB) or Network Load Balancer (NLB), target instances or container IPs in the Target Group fail health checks and are marked `Unhealthy`.
- **Client sees:** `HTTP 502 Bad Gateway` (ALB) or connection resets / TCP RST (NLB).
- **Target Group Console displays:** `Target.FailedHealthChecks` or `HealthCheck.Unhealthy`.
- **Impact:** Entire availability zones or backend services become unreachable.

## Immediate Diagnostic Checklist

### 1. Check Target Group Health via AWS CLI
```bash
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --query "TargetHealthDescriptions[].{Target:Target.Id,Port:Target.Port,State:TargetHealth.State,Reason:TargetHealth.Reason,Description:TargetHealth.Description}" \
  --output table
```

### 2. Verify Port & Protocol Accessibility from Within the VPC
```bash
# Test direct HTTP health check from a bastion or neighboring instance
curl -Iv http://<target-private-ip>:<health-check-port>/healthz
```

### 3. Review Security Group Rules
Verify whether:
1. Target instance Security Group allows inbound traffic from the Load Balancer Security Group.
2. Load Balancer Security Group allows outbound traffic to target instance ports.

## Root Causes & Triage Paths

### Scenario A: Target Security Group Lacks ALB SG Ingress Rule
Most common cause: Target instance allows traffic from port 80/443 publicly or from specific CIDRs, but forgets to reference the ALB's Security Group ID.
- **Immediate Fix:** Add ingress rule allowing ALB Security Group on the target port:
```bash
aws ec2 authorize-security-group-ingress \
  --group-id <target-instance-sg-id> \
  --protocol tcp \
  --port <target-app-port> \
  --source-group <alb-sg-id>
```

### Scenario B: Application Health Check Path Mismatch (404 Not Found)
The application expects `/healthz` or `/actuator/health`, but the Target Group configuration defaults to `/`. The backend returns `404 Not Found`, failing the default 200 OK expectation.
- **Immediate Fix:** Update Target Group health check path:
```bash
aws elbv2 modify-target-group \
  --target-group-arn <target-group-arn> \
  --health-check-path "/healthz" \
  --matcher "HttpCode=200,204"
```

### Scenario C: Backend Slow Startup Causing Premature Failure During Deployment
A Java Spring Boot or heavy application takes 45 seconds to boot, but Target Group `HealthCheckTimeoutSeconds` is 5s with `HealthyThresholdCount=2` and `UnhealthyThresholdCount=2`. The target is marked unhealthy before it finishes loading.
- **Immediate Fix:** Increase target group deregistration and health check grace periods:
```bash
aws elbv2 modify-target-group \
  --target-group-arn <target-group-arn> \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 5
```

## SRE Prevention & Checklist
1. Ensure all backend services expose a lightweight, dependency-free `/healthz` endpoint that does not query downstream databases on every health check ping.
2. In Kubernetes (AWS Load Balancer Controller), use `alb.ingress.kubernetes.io/healthcheck-path: /healthz` annotation.
3. Configure CloudWatch Alarms for `UnHealthyHostCount > 0` with PagerDuty notification.
