# Cells and Amp Documentation

## Overview

This document describes the relationship between Cells and Amp (a component of GitLab Dedicated tooling), explaining how Amp serves as the control plane for managing Dedicated Tenants, with each Cell representing a Dedicated Tenant.

## Amp Architecture

### Purpose and Functionality

[Amp](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/) is part of the dedicated tooling ecosystem that orchestrates the provisioning and lifecycle management of Dedicated Tenants (Cells) through Kubernetes clusters. It provides a control plane while using the [Instrumentor](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/instrumentor) service to execute the actual Cell deployments.

### Secret Management

Amp manages the lifecycle of environment-wide secrets, including but not limited to:

- `SMTP Configuration`
- `KAS_AGENT_CONNECT_TOKEN`
- `INSTRUMENTOR_REGISTRY_TOKEN`

These secrets are manually stored as `GitLab CI/CD variables` for the target environment. Terraform then consumes these variables to create downstream resources such as GCP or Kubernetes secrets. For example, the `TF_SECRETS_VAR_FILE` variable contains necessary Terraform secrets restricted to the `cellsdev` environment.

For more details on the principles and best practices around secrets management, please refer to the [Secrets Management Principles](https://gitlab-com.gitlab.io/gl-infra/gitlab-dedicated/team/engineering/Secrets-Management.html#principles) documentation.

### Service Account Configuration

Amp configures all required service accounts in GCP and establishes the necessary:

- IAM roles
- OIDC authentication
- Kubernetes cluster configuration

For detailed information about GitLab Dedicated architecture and tooling, refer to the [architecture](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/tree/main/architecture) and [engineering](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/tree/main/engineering) documentation.

### Environments Overview

We maintain two distinct Amp environments for Cells management:

| Environment | GCP Project (Kubernetes Cluster) | GCP Organization | Configuration Path |
| ------------- | -------------------------------- | ------------------ | ------------------- |
| Development (cellsdev) | [`amp-b6f1`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/blob/84b37222dcafcceebf271f32ea7f765734a2c7bc/environments/cellsdev/common.hcl#L21) | [`gitlab-cells.dev`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/blob/84b37222dcafcceebf271f32ea7f765734a2c7bc/environments/cellsdev/common.hcl#L22) | [`environments/cellsdev`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/tree/main/environments/cellsdev) |
| Production (cellsprod) | [`amp-3cod`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/blob/84b37222dcafcceebf271f32ea7f765734a2c7bc/environments/cellsprod/common.hcl#L21) | [`gitlab-cells.com`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/blob/84b37222dcafcceebf271f32ea7f765734a2c7bc/environments/cellsprod/common.hcl#L22) | [`environments/cellsprod`](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/tree/main/environments/cellsprod) |

## Environment Management

### Bootstrap Process

All Amp environments, including the Cells environments, are bootstrapped via GitLab CI pipelines. The process initializes the necessary infrastructure and configures the Kubernetes clusters that will host the Amp control plane.

Please refer to [Amp Environment Bootstrap](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/#amp-environment-bootstrap) to know more about the complete bootstrapping process.

### Terraform State

Each environment maintains its own Terraform state stored in GitLab.com's Terraform state storage. The state files are managed at [https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/terraform](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/terraform). This ensures proper separation between environments and prevents cross-environment changes.

## Cell Deployment

### CI/CD Integration

The deployment of Cells leverages the Amp Kubernetes clusters through the [`cells/tissue`](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue) CI/CD pipelines.

### KAS Agents

Cell deployments use [KAS agents](https://docs.gitlab.com/user/clusters/agent/) to trigger the deployment process. The KAS secrets are stored in the CI/CD variables of the Amp project, ensuring secure communication between the CI pipelines and the Kubernetes clusters.

## Operational Considerations

### Scaling Amp Clusters

Since the Amp clusters run QA jobs for all cells, they occasionally encounter scaling limitations. Common solutions include:

- Increasing the number of nodes in the cluster
- Provisioning larger node types

For an example of cluster scaling, see [this merge request](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/-/merge_requests/1607).

### Access Management

Access to the Cells environments is managed through [PAM entitlements](https://docs.cloud.google.com/iam/docs/pam-overview), which allow for controlled escalation of privileges to the `cellsdev` or `cellsprod` GCP organizations.

> **Note:** Team members must be connected to NordLayer VPN to access the Amp Kubernetes clusters. For setup and usage instructions, refer to the [NordLayer guide](https://internal.gitlab.com/handbook/it/it-self-service/it-guides/nordlayer/).

### Breakglass Procedures

For emergency access to the Cell/Amp projects or organizations, refer to the [Breakglass](./breakglass.md) documentation, which outlines when and how to properly access these resources.

## Additional Resources

For more information about GitLab Dedicated and related tooling, refer to:

- [GitLab Dedicated Architecture Documentation](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/tree/main/architecture)
- [GitLab Dedicated Engineering Documentation](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/team/-/tree/main/engineering)
- [Amp Repository](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/amp/)
- [Instrumentor Repository](https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/instrumentor)
