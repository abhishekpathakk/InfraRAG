# Topology Service: On-Call Survival Guide

> [!important]
> This guide is structurally complete but contains placeholder threshold values pending performance testing results. Use with caution until placeholders are replaced with actual operational values.

This guide helps on-call engineers respond to [Topology Service](https://gitlab.com/gitlab-org/cells/topology-service) incidents. It assumes you're familiar with SLIs, error budgets, and cloud platforms (GCP), but have no prior knowledge of Topology Service.

## What is Topology Service?

**Topology Service** is the central coordination system for GitLab Cells, providing three critical services that enable routing, global uniqueness, and cell provisioning. It runs in two deployment modes: **REST API** ([topology-rest](../topology-rest/README.md)) for HTTP Router and **gRPC API** ([topology-grpc](../topology-grpc/README.md)) for internal cell operations. It is deployed from [topology-service-deployer](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer) and is deployed via [Runway](https://docs.runway.gitlab.com/). Runway itself orchestrates the deployments via 'deployment projects' ([topology-rest](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/deployments/topology-rest) & [topology-grpc](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/deployments/topology-grpc))

### Three Core Services & Failure Impacts

| Service | Purpose | Code Path | Deployment | Impact When Down |
| ------- | ------- | --------- | ---------- | ---------------- |
| **ClassifyService** | REST (Routes requests to correct cell) | [`internal/services/classify/`](https://gitlab.com/gitlab-org/cells/topology-service/-/tree/main/internal/services/classify) | REST | **CRITICAL:** All routing broken, no requests reach cells<sup>[1](#fn1)</sup> |
| **ClaimService** | Ensures global uniqueness (usernames, emails, namespaces) | [`internal/services/claim/`](https://gitlab.com/gitlab-org/cells/topology-service/-/tree/main/internal/services/claim) | gRPC only | Cannot create users/groups/projects, transactions fail |
| **SequenceService** | Allocates non-overlapping ID ranges during cell provisioning | [`internal/services/cell/`](https://gitlab.com/gitlab-org/cells/topology-service/-/tree/main/internal/services/cell) | gRPC only | Cannot provision new cells |

**Footnotes:**
<a name="fn1"></a>**[1]** ClassifyService failure is gradual - routing degrades as cache expires. Indicators: decreased (not zero) cell-local traffic, 404 spike from legacy cell fallback.

**Key takeaway for on-call:** ClassifyService affects routing (immediate user impact), ClaimService affects writes (no routing impact but increases database transaction failure), SequenceService affects only new cell provisioning.

**Critical dependency:** All services rely on Cloud Spanner. Spanner CPU/connection issues cascade to all three services.

**Architecture in Brief:**

![Cells Architecture](../cells/img/cells-architecture.png)

Topology Service design: <https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/cells/topology_service/>

## Quick Reference Card

### Key Resources

- **Dashboards:** [gRPC Prod](https://dashboards.gitlab.net/d/topology-grpc-main/topology-grpc3a-overview) | [REST Prod](https://dashboards.gitlab.net/d/topology-rest-main/topology-rest3a-overview) | [Spanner Prod](https://dashboards.gitlab.net/d/topology-spanner-main/topology-spanner3a-overview) | [RBAC Auth](https://dashboards.gitlab.net/d/topology-grpc-auth-monitoring/topology-grpc-rbac-authentication-monitoring)
- **Deployment:** [topology-service-deployer](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer)
- **Source:** [topology-service](https://gitlab.com/gitlab-org/cells/topology-service)
- **Cloud Run:** [Production Console](https://console.cloud.google.com/run?project=gitlab-runway-topo-svc-prod)
- **Spanner:** [Production Console](https://console.cloud.google.com/spanner?project=gitlab-runway-topo-svc-prod)
- **Runway Deployment Projects:** [topology-grpc](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/deployments/topology-grpc) , [topology-rest](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/deployments/topology-rest) , [topology-migrate](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/deployments/topology-migrate)
- **Logs:** [Grafana Logs [REST]](https://dashboards.gitlab.net/goto/cf63hvdar0ruod?orgId=1), [Grafana Logs [GRPC]](https://dashboards.gitlab.net/goto/VErIPujHg?orgId=1), [Cloud Logging Spanner](https://cloudlogging.app.goo.gl/DwesPX7SQLjDKt5NA)

### Emergency Access

For infrastructure-level troubleshooting, Cloud Spanner logs, or emergency rollbacks via Cloud Run UI, you'll need Breakglass access to the GCP Console:

- [Cloud Logging](https://cloudlogging.app.goo.gl/DwesPX7SQLjDKt5NA) for Cloud Spanner
- [Cloud Run Console](https://console.cloud.google.com/run?referrer=search&project=gitlab-runway-topo-svc-prod) for container-level operations

**GCP Console (UI):**

- [Production PAM](https://console.cloud.google.com/iam-admin/pam/entitlements/my?project=gitlab-runway-topo-svc-prod)
- Click "Request Access" → Select `breakglass-entitlement-gitlab-runway-topo-svc-prod` → Enter incident link → Submit

**gcloud CLI (Breakglass):**

```bash
# Production
gcloud beta pam grants create \
  --entitlement="breakglass-entitlement-gitlab-runway-topo-svc-prod" \
  --requested-duration="1800s" \
  --justification="$INCIDENT_LINK" \
  --location=global \
  --project="gitlab-runway-topo-svc-prod"
```

> [!note]
> You will need to have Breakglass entitlement from [PAM](https://docs.cloud.google.com/iam/docs/pam-overview) to access GCP Console resources (such as GCP Logs). See [breakglass](../cells/breakglass.md) for help.

### Emergency Contacts

- **Topology Service + Spanner:** [`Cells`](https://handbook.gitlab.com/handbook/product/categories/lookup/)
- **Immediate help:** [`#g_cells_infrastructure`](https://gitlab.enterprise.slack.com/archives/C07URAK4J59)
- **Business hours:** [`#f_protocells`](https://gitlab.enterprise.slack.com/archives/C0609EXHX6F)

## Component Overview & Common Failures

| Component | What It Does | Dashboard | Logs |
| --------- | ------------ | --------- | ---- |
| **REST API** (topology-rest) | HTTP endpoint for HTTP Router to classify requests | [REST Dashboard](https://dashboards.gitlab.net/d/topology-rest-main/topology-rest3a-overview) | [Grafana Logs](https://dashboards.gitlab.net/goto/VErIPujHg?orgId=1) & [Cloud Run Logs](https://cloudlogging.app.goo.gl/o692A1WQFKsc6eNX9) |
| **gRPC API** (topology-grpc) | Internal API for cells: claim resources, classify, manage ID sequences | [gRPC Dashboard](https://dashboards.gitlab.net/d/topology-grpc-main/topology-grpc3a-overview) | [Grafana Logs](https://dashboards.gitlab.net/goto/cf63hvdar0ruod?orgId=1) & [Cloud Run Logs](https://cloudlogging.app.goo.gl/CAagU7Wk7SoqCxpSA) |
| **Cloud Spanner** | Stores classifications, claims, ID sequences | [Spanner Dashboard](https://dashboards.gitlab.net/d/topology-spanner-main/topology-spanner3a-overview) | [Cloud Logging](https://cloudlogging.app.goo.gl/DwesPX7SQLjDKt5NA) |

### Alert Types & Response

| Alert | Think | Check |
| ----- | ----- | ----- |
| **ApdexSLOViolation** (gRPC/REST) | Requests too slow or failing | Spanner → Service Service Panel → Spanner Service Logs |
| **ErrorSLOViolation** (gRPC/REST) | Service returning errors | Service logs → Spanner status → Recent deployments |
| **TrafficCessation** (gRPC/REST) | No traffic (was flowing 1hr ago) | Cloud Run instances → Deployment pipeline |
| **Regional** (suffix) | Single region problem | Same as above, region-specific |
| **AuthRequestsApdexSLOViolation** | mTLS auth taking too long | Check cert chain complexity → policy evaluation overhead → [RBAC Auth Dashboard](https://dashboards.gitlab.net/d/topology-grpc-auth-monitoring/topology-grpc-rbac-authentication-monitoring) |
| **AuthRequestsErrorSLOViolation** | mTLS auth failures elevated | Check cert validity/expiry → RBAC policies → recent deployments → `auth_requests_total{status="failure"}` by `reason` label |

**Mental models:**

- **High latency?** Example: think Spanner CPU → Spanner resource limits → Network
- **Errors?** Example: think Spanner connection → Service crash → Bad deployment
- **No traffic?** Example: think Instances down → Load balancer → Deployment
- **Post-deployment weirdness?** Check: Recent deployments → Service logs → Spanner status

## Deployment Procedures

**Never rollback. Always roll forward.** Spanner schema migrations are one-way only.

**Why We Roll Forward Only**
Topology Service uses a dual-codebase deployment pattern and Cloud Spanner schema migrations. Rolling back code risks:

 (1) deployment/application version mismatches causing failed deploys.

 (2) schema incompatibility causing startup failures or database corruption during the zero-instance deployment window.

To recover safely in the event of an incident and a code change is suspected as the root cause:

- Create a revert, branch from known-good code, rebase onto main, add forward-compatible schema changes if needed, then deploy normally. Asking for approvals normally.

>[!important]
> In case of emergencies or when maintainers are unavailable, rollback can be performed from the CloudRun UI. These are rollbacks should be done using the EOC's best judgment and verifying the [last few commits on the Topology Service](https://gitlab.com/gitlab-org/cells/topology-service/-/commits/main). The application is normally compatible with the N+1 schema change.

- **Transient failures:** Retry pipeline stage in [topology-service-deployer](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer/-/pipelines)
- **Code issues:** Push fix via MR to [topology-service](https://gitlab.com/gitlab-org/cells/topology-service) or [deployer](https://ops.gitlab.net/gitlab-com/gl-infra/cells/topology-service-deployer)
- **Critical bugs:** Revert commit in Git, deploy the revert

## Metrics Quick Reference

Two independent metric paths:

- **Application:** `{job="topology-service", type="topology-[grpc|rest]", environment="gprd"}` - Business logic, gRPC method stats
  - [GRPC Query in Grafana Explore](https://dashboards.gitlab.net/goto/af66ojje7sd1ca?orgId=1) & [REST Query in Grafana Explore](https://dashboards.gitlab.net/goto/ff66oot0i1x4wb?orgId=1)

- **Infrastructure:** `{job="runway-exporter", project_id="gitlab-runway-topo-svc-prod"}` - Cloud Run CPU/memory, Spanner metrics
  - [Query in Grafana Explore](https://dashboards.gitlab.net/explore?...) <!-- *(convenience link)* -->

- **RBAC Authentication:** `{job="topology-service", type="topology-grpc"}` — mTLS auth metrics (gRPC only)
  - `auth_requests_total{status, reason, rpc_method, rpc_service}` — auth success/failure counts
  - `policy_failures_total{reason, rpc_method, rpc_service}` — RBAC policy violations
  - `auth_request_duration_seconds_bucket{rpc_method, rpc_service}` — auth latency histogram
  - [RBAC Auth Dashboard](https://dashboards.gitlab.net/d/topology-grpc-auth-monitoring/topology-grpc-rbac-authentication-monitoring)

Query via [Grafana Explore](https://dashboards.gitlab.net/explore) (mimir-runway datasource).

## Remember

- **Access expires:** Please remember that PAM grants do have a duration
- **Document everything:** Add findings to incident timeline
- **Escalate early:** Team prefers early escalation over solo struggle
- **Roll forward, never rollback:** Always deploy fixes via new commits
- **When in doubt:** Ask in [#g_cells_infrastructure](https://gitlab.enterprise.slack.com/archives/C07URAK4J59) or [#f_protocells](https://gitlab.enterprise.slack.com/archives/C0609EXHX6F)
