# Teleport Administration

This page is the primary reference for Teleport infrastructure administration at
GitLab. It covers architecture, deployment, configuration, security, and
integrations at a high level.

For end-user runbooks (e.g. how to access a rails console), see
[Teleport](./README.md#user-guides)

## Admin operations

| Runbook                                                          | Description                                                   |
| ---------------------------------------------------------------- | ------------------------------------------------------------- |
| [Check Cluster Status](admin/teleport_check_status.md)           | Verify health of the Teleport cluster and its components      |
| [Add a Resource](admin/teleport_add_resource.md)                 | Register a new SSH node or database with the Teleport cluster |
| [Rotate Enterprise License](admin/teleport_rotate_license.md)    | Renew and apply an updated Teleport Enterprise license        |
| [Slack Integration](admin/teleport_slack_integration.md)         | Maintain the Slack plugin for access request notifications    |
| [Terraform Integration](admin/teleport_terraform_integration.md) | Maintain the Terraform provider auth identity                 |
| [SIEM Integration](admin/teleport_siem_integration.md)           | Maintain the audit event export pipeline to Fluentd/SIEM      |
| [Disaster Recovery](teleport_disaster_recovery.md)               | Disaster recovery procedures                                  |

## Overview

### What problem does Teleport solve?

Traditional infrastructure access relies on long-lived SSH keys or shared
passwords that are difficult to audit, store, issue, rotate, and revoke.

Teleport solves this by acting as a **certificate authority (CA)**. Rather than
deploying permanent credentials like an SSH key, it issues on-demand short-lived
certificates to users. Users authenticate with Teleport via single sign-on like
Okta, allowing fine-grained role-based access policies to determine which
resources they can access.

Every action taken through Teleport — logins, executed commands, database
queries — is also recorded in a tamper-evident audit log, and interactive
sessions can be fully replayed.

### How GitLab uses Teleport

GitLab runs a self-hosted Teleport Enterprise Edition cluster on Google Cloud.
It is the primary mechanism used by GitLab engineers to access to production
virtual machines, databases, Kubernetes clusters, and Rails consoles across both
non-production and production environments.

Teleport access is controlled via **Okta group membership**. Okta groups are
mapped directly to Teleport roles. Teleport roles specify the resources that may
be accessed and which actions can be taken. Some access (e.g. non-production
read-only) is granted by default; sensitive access (e.g. production databases)
require explicit just-in-time access requests, which are valid for 12 hours and
must be approved by a manager.

## Architecture

### Core model

A Teleport deployment has four key components:

1. **Teleport cluster** — the control plane. It authenticates users, issues
   certificates, enforces access policies, and collects audit events. The cluster
   has two services: the **Auth Service** (the CA and policy engine) and the
   **Proxy Service** (the single gateway all traffic flows through).

2. **Teleport agents** — lightweight processes deployed alongside infrastructure
   resources (VMs, databases, Kubernetes clusters). They register those resources
   with the cluster and enforce access policies. Agents connect _outward_ to the
   Proxy via a reverse tunnel — resources behind firewalls never need inbound rules
   opened.

3. **Teleport clients** — engineers using `tsh` (CLI) or the [web
   UI](https://production.teleport.gitlab.net/web). A client authenticates via SSO,
   receives a short-lived certificate from the Auth Service, then connects to a
   resource through the Proxy. The agent on the other end verifies the certificate
   and grants access according to the user's roles.

4. **Teleport bots (a.k.a. Machine & Workload Identity)** — the machine
   equivalent of a human client. Rather than a human authenticating via SSO, `tbot`
   runs as a daemon alongside automated workloads (CI/CD pipelines, services,
   scripts) and continuously fetches and renews short-lived credentials from the
   Auth Service. This allows applications to access resources via teleport, or
   authenticate with each other, without any long-lived credentials. See
   [Machine & Workload Identity](https://goteleport.com/docs/machine-workload-identity/introduction/)
   in Teleport's docs.

See [Teleport core concepts](https://goteleport.com/docs/core-concepts/) for a
deeper explanation.

### Agents

We currently deploy Teleport Agents on most GitLab.com GCP virtual machines (via
Chef) and Kubernetes clusters (via ArgoCD).

### Clusters

We run two Teleport clusters. The production cluster runs in `us-central1` — (a
different region from our primary infrastructure (`us-east1`) — so the cluster
remains reachable even during a regional failure.

| Cluster    | URL                                                                      | GKE Cluster      | GCP Project                  | Region        | Purpose                                                      |
| ---------- | ------------------------------------------------------------------------ | ---------------- | ---------------------------- | ------------- | ------------------------------------------------------------ |
| Production | [production.teleport.gitlab.net](https://production.teleport.gitlab.net) | `ops-central`    | `gitlab-teleport-production` | `us-central1` | All GitLab infrastructure access (inc. staging and pre-prod) |
| Staging    | [staging.teleport.gitlab.net](https://staging.teleport.gitlab.net)       | `ops-gitlab-gke` | `gitlab-teleport-staging`    | `us-east1`    | Testing, upgrades, DR validation                             |

### Cluster services

Each Teleport cluster consists of several services. Both the Auth and Proxy
services run in high-availability mode. See [Teleport architecture
docs](https://goteleport.com/docs/architecture/) for more detail.

| Component               | Role                                                                                                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Auth Service**        | The certificate authority (CA) for the cluster. Issues certificates to clients and nodes, collects audit events, and stores them. Configured via the [`tctl`](https://goteleport.com/docs/reference/cli/tctl/) CLI. |
| **Proxy Service**       | The client gateway, and only cluster component exposed to the internet. All client connections and protocol traffic flow through it; also serves the Web UI and allows remote nodes to establish reverse tunnels.   |
| **Kubernetes Operator** | Manages Teleport resources (roles, users, etc.) via Kubernetes custom resources, following the [Operator Pattern](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/).                                 |

### Cluster plugins

Plugins extend the Teleport cluster with additional features and run as separate
workloads alongside the cluster services.

| Plugin                            | Purpose                                                                                                                                                        |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **teleport-plugin-slack**         | Notifies [#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM) and tagged individuals when access requests are submitted or resolved. |
| **teleport-plugin-event-handler** | Streams audit events to a Fluentd instance for SIEM ingestion.                                                                                                 |

## Deployment & Configuration

All deployment & configuration is achieved via infrastructure-as-code tooling.

| Layer              | Tooling   | Source                                                                                                                                                                                                                                                                   | What it manages                                                                                                                           |
| ------------------ | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| GKE workloads      | Helm      | [apps/services/teleport-cluster](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/teleport-cluster), [apps/services/teleport-agent](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/teleport-agent?)                      | Teleport cluster deployment & config, Teleport agent deployment & config (Kubernetes resources only)                                      |
| GCP infrastructure | Terraform | [config-mgmt/teleport-production](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/teleport-production), [config-mgmt/teleport-staging](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/teleport-staging) | Teleport cluster config (user group & role management), Deployment of GCP resources needed by Teleport cluster (KMS, Firestore, GCS, etc) |
| VM configuration   | Chef      | [gitlab-teleport cookbook](https://gitlab.com/gitlab-cookbooks/gitlab-teleport)                                                                                                                                                                                          | Teleport agent deployment & config (on VMs)                                                                                               |

### Deployment overview

![GitLab Teleport Architecture](./images/teleport-arch.png)

## Data Storage

Teleport agents and the Proxy Service are stateless. All durable state is held
by the Auth Service. For backup and restore procedures, see the [Disaster Recovery](teleport_disaster_recovery.md) runbook.

| Data                         | Storage                                                                                                                                                 | Notes                                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Cluster state & audit events | [Firestore](https://console.cloud.google.com/firestore/databases/-default-?project=gitlab-teleport-production)                                          | Backed up daily; 90-day retention (production), 30-day (staging)                                    |
| Session recordings           | [Cloud Storage](https://console.cloud.google.com/storage/browser/gl-teleport-production-teleport-sessions?project=gitlab-teleport-production)           | Multi-region bucket with versioning and soft deletion; objects transition to Nearline after 30 days |
| CA private keys              | [Cloud KMS](https://console.cloud.google.com/security/kms/keyring/manage/us/gitlab-teleport-teleport-production/key?project=gitlab-teleport-production) | See [Secrets Management](#secrets-management)                                                       |
| Operational secrets          | [Vault](https://vault.gitlab.net) (`k8s/ops-central/teleport-cluster-production/`)                                                                      | See [Secrets Management](#secrets-management)                                                       |
| Audit event stream           | [Cloud Pub/Sub](https://cloud.google.com/pubsub/)                                                                                                       | Topics: `teleport-production-events`, `teleport-staging-events`                                     |

## Security

### Authentication

All internal communication between cluster components (Auth Service, Proxy,
agents, plugins) uses TLS mutual authentication. No component trusts another
without a valid certificate signed by the cluster's CA. See [Teleport
authentication docs](https://goteleport.com/docs/reference/architecture/authentication/).

Agents need to authenticate with the cluster when they are first deployed. They
do this via a [join
token](https://goteleport.com/docs/reference/deployment/join-methods/).
Temporary static tokens were previously used for this purpose. They were
generated via Terraform and stored in Vault, where they were retrieved by the
[gitlab-teleport](https://gitlab.com/gitlab-cookbooks/gitlab-teleport) Chef
cookbook. These have now been replaced by dynamic join tokens (most use GCP
service account, but some integrations use Kubernetes).

At GitLab, human users authenticate via **Okta (SAML)**. Service accounts
(plugins, CI, integrations) use Teleport's Machine & Workload Identity.

### Authorization

Teleport uses [Role-Based Access Control
(RBAC)](https://goteleport.com/docs/reference/architecture/authorization/) to manage
access to resources.

At GitLab, a user's Okta groups are supplied to Teleport each time they
authenticate (via SAML). Those groups are mapped directly to roles in Teleport's
config. These group->role mappings are currently defined in
[config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments/teleport-production).

Sensitive access requires a [just-in-time access
request](https://goteleport.com/docs/identity-governance/access-requests/),
which grants temporary access and must be approved by an authorized approver.

### Audit

The Teleport Auth Service writes audit events to a GCP Firestore table, and full
interactive sessions are recorded to Google Cloud Storage. Sessions can be
replayed for compliance or incident investigation. Events are also streamed to
an external SIEM via the event-handler plugin (see [Integrations](#integrations)).

### Secrets Management

**CA private keys** are managed entirely by [Google Cloud
KMS](https://goteleport.com/docs/installation/self-hosted/private-keys/gcp-kms/).
Teleport generates key material inside KMS and stores only the key reference —
private keys never leave KMS. GCP automatically backs up all KMS key material.

**Operational secrets** (enterprise license, plugin auth identities, TLS
certificates) are stored in [Vault](https://vault.gitlab.net) and synced into
Kubernetes as secrets via the External Secrets Operator.

## Integrations

### Slack

Deployed via the
[`teleport-plugin-slack`](https://goteleport.com/docs/reference/helm-reference/teleport-plugin-slack/)
Helm chart. Previously used a dedicated `slack` service account whose auth
identity is stored in Vault, it now uses Teleport's Machine & Workload Identity
to authenticate.

See [Slack Integration runbook](admin/teleport_slack_integration.md) for
maintenance procedures.

### Terraform

The [Teleport Terraform
provider](https://goteleport.com/docs/admin-guides/infrastructure-as-code/terraform-provider/)
manages Teleport resources (roles, users, etc.) as code in config-mgmt.
Previously used a dedicated `terraform` service account whose auth identity is
stored in Vault and consumed by CI pipelines, it now uses Teleport's Machine &
Workload Identity to authenticate.

See [Terraform Integration runbook](admin/teleport_terraform_integration.md) for
maintenance procedures.

### SIEM

Deployed via the
[`teleport-plugin-event-handler`](https://goteleport.com/docs/reference/helm-reference/teleport-plugin-event-handler/)
Helm chart. Communicates with [Fluentd](https://www.fluentd.org/) over mTLS;
Fluentd forwards events to Cloud Pub/Sub (`teleport-production-events` /
`teleport-staging-events` topics) for downstream SIEM consumption.

See [SIEM Integration runbook](admin/teleport_siem_integration.md) for
maintenance procedures.
