# Blue_Green_Deployment

This document outlines the blue/green deployment strategy where we maintain a single active cluster serving production traffic. The inactive cluster sits around awaiting a new deployment, before becoming active again.

While troubleshooting or working with blue-green deployments you might need to:

## Identifying the Current Active Deployment

To determine which deployment is currently active:

1. Access the [Grafana Dashboards](https://dashboards.gitlab.net/login).
2. Open the [CI Runners Deployment Overview Dashboard](https://dashboards.gitlab.net/d/ci-runners-deployment/ci-runners3a-deployment-overview?orgId=1).
3. Locate the 'instance' column in the 'GitLab Runner Versions' section to identify the active deployment.

## Executing ChatOps Commands

Use ChatOps commands in the #production channel to manage deployments. It's crucial to deploy only one environment (blue or green) at a time.
The ChatOps commands logic lives in the [Deployer repo](https://gitlab.com/gitlab-com/gl-infra/ci-runners/deployer)

### Deploying and Draining Runner Managers

1. **Deploy the Green Environment (When Blue is Active):** This command enables and executes chef-client on the green deployment to install the [GitLab Runner version](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/runners-manager-private-blue.json#L13) defined in the [Chef repository](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/runners-manager-private-blue.json). It also starts the GitLab Runner service.

    `/runner run start private green`

2. **Drain the Blue Environment (After Green is Deployed):** This command initiates the process of draining the runners and deleting the machines in the blue environment. This operation may take several hours up to a full day to complete.

    `/runner run stop private blue`

A list of all the the available commands can be found in [Deployer repo](https://gitlab.com/gitlab-com/gl-infra/ci-runners/deployer/-/blob/main/.gitlab-ci.yml#L102-115)

## Support and Queries

For any questions or support,  reach out to folks in #g_runner_saas Slack Channel.
