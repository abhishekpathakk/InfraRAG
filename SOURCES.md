# InfraRAG Document Corpus & Attribution Sources

This document provides a registry of all external public and internal incident runbook sources ingested into the **InfraRAG** vector knowledge base, including repository URLs, component scope, and open-source licenses.

---

## Corpus Overview

| Source Identifier | Type | Origin Repository | Extracted Path | Ingested Topics | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`internal`** | `internal` | Local Repository | `data/internal/` | Kubernetes OOMKilled, CrashLoopBackOff, NodeDiskPressure, Ingress 504, Istio 503, STRICT mTLS, Docker Space, AWS NLB | Apache 2.0 |
| **`kubernetes`** | `public` | [kubernetes/website](https://github.com/kubernetes/website) | `data/public/kubernetes/` | Pod Lifecycle, Container Debugging, Cluster Troubleshooting, Ephemeral Containers | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| **`istio`** | `public` | [istio/istio.io](https://github.com/istio/istio.io) | `data/public/istio/` | Envoy Proxy Diagnostics, Service Mesh Connectivity, Ingress/Egress Troubleshooting, Traffic Management | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| **`gitlab`** | `public` | [gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks) | `data/public/gitlab/` | Production SRE Incident Runbooks, Patroni/Postgres Failover, Gitaly Storage, Sidekiq Queue Saturation | [MIT License](https://gitlab.com/gitlab-com/runbooks/-/blob/master/LICENSE) |

---

## Detailed Source Registries

### 1. Internal Incident Runbooks (`type=internal`)
- **Directory:** [data/internal/](file:///Users/abhishekpathak/Desktop/Abhishek/Repos/RAG/data/internal)
- **Description:** Curated, actionable, operational runbooks authored specifically for production incident response and automated remediation.
- **Coverage:**
  - `kubernetes_oom_killed.md` (Exit Code 137, Cgroups, JVM flags)
  - `kubernetes_crashloopbackoff.md` (Exit Codes 1, 139, 143, Probe failures)
  - `kubernetes_node_disk_pressure.md` (Kubelet evictions, ephemeral storage, image pruning)
  - `kubernetes_ingress_504_gateway_timeout.md` (Nginx Ingress / ALB timeouts, connection draining)
  - `istio_503_service_unavailable.md` (Envoy UF/UC response flags, proxy synchronization)
  - `istio_mtls_strict_failures.md` (PeerAuthentication STRICT vs DestinationRule ISTIO_MUTUAL)
  - `docker_daemon_out_of_space.md` (Docker overlay2 block/inode exhaustion, daemon.json rotation)
  - `aws_network_load_balancer_unhealthy_hosts.md` (Target.FailedHealthChecks, Security Group mismatches)

---

### 2. Kubernetes Documentation (`type=public`, `source=kubernetes`)
- **Repository URL:** [https://github.com/kubernetes/website](https://github.com/kubernetes/website)
- **Upstream Documentation:** [https://kubernetes.io/docs/](https://kubernetes.io/docs/)
- **License:** Creative Commons Attribution 4.0 International ([CC BY 4.0](https://github.com/kubernetes/website/blob/main/LICENSE))
- **Ingestion Scope:**
  - `content/en/docs/tasks/debug/` (Application debugging, cluster troubleshooting, coredns diagnostics)
  - `content/en/docs/concepts/workloads/pods/` (Pod lifecycle, container restart policies, termination status)

---

### 3. Istio Service Mesh Documentation (`type=public`, `source=istio`)
- **Repository URL:** [https://github.com/istio/istio.io](https://github.com/istio/istio.io)
- **Upstream Documentation:** [https://istio.io/latest/docs/](https://istio.io/latest/docs/)
- **License:** Creative Commons Attribution 4.0 International ([CC BY 4.0](https://github.com/istio/istio.io/blob/master/LICENSE))
- **Ingestion Scope:**
  - `content/en/docs/ops/` (Operational tools, diagnostic commands, envoy access log analysis, MTLS troubleshooting)

---

### 4. GitLab Production Runbooks (`type=public`, `source=gitlab`)
- **Repository URL:** [https://gitlab.com/gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks)
- **Upstream Documentation:** [https://gitlab.com/gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks)
- **License:** MIT License ([Code](https://gitlab.com/gitlab-com/runbooks/-/blob/master/LICENSE)) / CC BY-SA 4.0 (Documentation)
- **Ingestion Scope:**
  - `docs/` (High-availability database failovers, background worker queue saturation, network partition mitigations)

---

## Metadata Model Schema
Every chunk extracted across these sources is assigned structured metadata:
```json
{
  "chunk_id": "k8s_debug_pod-c1",
  "source": "kubernetes",
  "path": "data/public/kubernetes/debug-pod.md",
  "section": "Determine the reason for Pod termination",
  "type": "public",
  "token_count": 312
}
```
Query-time filtering (`type=internal` or `type=public`) is supported directly in retrieval APIs and UI toggles.
