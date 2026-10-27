## GitLab Runner Projects Overview

GitLab's hosted runners infrastructure consists of multiple interconnected repositories and services that work together to provide scalable CI/CD execution environments. This documentation covers the GitLab projects, their relationships, and where to find configuration details.

### Core Runner Infrastructure

**[GitLab Runner Core Application](https://gitlab.com/gitlab-org/gitlab-runner)**: The main GitLab Runner application that executes CI/CD jobs.

**[Fleeting Plugin](https://gitlab.com/gitlab-org/fleeting/fleeting)**: Plugin system for dynamic runner provisioning.

**[Nesting](https://gitlab.com/gitlab-org/fleeting/nesting)**: Basic and opinionated daemon that sits in front of virtualization platforms. Provides abstraction layer for managing virtual machines and containers.

**[Taskscaler](https://gitlab.com/gitlab-org/fleeting/taskscaler)**: Autoscaler for provisioning instances via fleeting. Handles allocation and assignment of tasks to provisioned instances.

**[Docker Machine](https://gitlab.com/gitlab-org/ci-cd/docker-machine)**: A fork of the Docker Machine project, used for autoscaling.

### Image Management

**[Job Images](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/job-images)**: Builds and maintains macOS images for use with nesting on macOS Runners in AWS.

**[macOS Nesting Images](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macos-nesting)**: Specialized images for macOS runner host environments.

**[Macos Image Inventory](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/macos-image-inventory)**: Creates a static site documenting notable software versions for each supported macos image.

**[Windows Containers](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/gcp/windows-containers)**: Images used by GitLab CI custom executor to run Jobs inside of Google Cloud Platform.

**[Linux COS](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/gcp/linux-cos)**: Customized build of Google COS image used by GitLab SaaS Linux runners.

### Grit Ecosystem

**[Grit](https://gitlab.com/gitlab-org/ci-cd/runner-tools/grit)**: Core tool for runner management and configuration.

**[Grit Images](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/grit-images)**: Builds images used within grit configurations.

**[Grit E2E Testing](https://gitlab.com/gitlab-org/ci-cd/runner-tools/grit-e2e)**: End-to-end testing for grit CI pipelines.

## Infrastructure Configuration

### Operations Repositories

**[Chef Repository](https://gitlab.com/gitlab-com/gl-infra/chef-repo)**: Contains Chef cookbooks and configuration management.

**[Operations Config Management](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt)**: Primary operations configuration and Terraform infrastructure management.

**[Windows CI Infrastructure](https://ops.gitlab.net/gitlab-com/gl-infra/ci-infrastructure-windows)**: archived. Ansible for the Windows manager VMs, which were replaced by pods in 2026-10, see [Windows runners](./windows/README.md).

### Chef Configuration

**[Base Runner Manager Definition](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/f2b7e351b4fcd0733db334258e499e79e9990a58/roles/runners-manager.json)**

- Path: `roles/runners-manager.json`

There are many more runner manager definitions in the same path with `runners-manager.json`. Their filenames all have the prefix of `runners-manager`.
