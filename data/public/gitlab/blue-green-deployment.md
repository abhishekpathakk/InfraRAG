# Blue Green Deployments

## Background

The runner deployment follows the [blue green
deployment](https://docs.aws.amazon.com/pdfs/whitepapers/latest/blue-green-deployments/blue-green-deployments.pdf) style.

[The Deployer](https://gitlab.com/gitlab-com/gl-infra/ci-runners/deployer/) was created as a way to automate this process through the slack controlled command `/runner`.

## Supported shards

- `private`
- `shared-gitlab-org`
- `saas-linux-large-amd64`
- `saas-linux-xlarge-amd64`
- `saas-linux-2xlarge-amd64`
- `saas-linux-medium-amd64-gpu-standard`
- `saas-linux-medium-amd64`
- `saas-linux-small-amd64`
- `saas-linux-small-arm64`
- `saas-linux-medium-arm64`
- `saas-linux-large-arm64`
- `saas-macos-staging`
- `saas-macos-medium-m1`
- `saas-macos-large-m2pro`

For a list of all shards see [deployer/bin/ci](https://gitlab.com/gitlab-com/gl-infra/ci-runners/deployer/-/blob/main/bin/ci#L46-60).

## Glossary

- `chef-repo`: <https://gitlab.com/gitlab-com/gl-infra/chef-repo> where
  all chef configuration is located.
- `terraform`:
  <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt> where all
  the terraform code is located.
- `deployment`: Referring if `blue` or `green` is active, it can also be
  both.

## Chef roles

See `runner-manager*` list under [chef-repo/roles](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/roles)

## Deployment Example

**WARNING: NEVER DEPLOY THE WHOLE RUNNER FLEET AT ONCE, ONLY DEPLOY EITHER THE BLUE OR THE GREEN**

We will give an example of how to deploy from `17.0.0~pre.88.g761ae5dd-1` to `17.7.0~pre.103.g896916a8-1` on
the `private` shard.

1. Identify the active deployment via the [ci-runners:: Deployment overview](https://dashboards.gitlab.net/goto/DJ5ZQOAHR?orgId=1) dashboard, let's assume the active deployment is `blue`.
1. Open a merge request to `chef-repo` to update the version for the
`green` deployment. :point_right: <https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/5383>
    1. Make sure the merge request has the `~deploy` and
    `~group::hosted runners` labels.
1. Make sure that the package for version `17.7.0~pre.103.g896916a8-1` [is published](https://packages.gitlab.com/app/runner/unstable/search?q=17.7.0~pre.103.g896916a8-1_amd64&dist=ubuntu)
1. Gather approval from the EOC via #production

    ```
    @sre-oncall I'm going to perform GitLab Runner version upgrade on two shards.
    Details in https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/5383.

    May I proceed? If yes, please approve the Merge Request.
    ```

1. Get the [merge request](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/5383) merged.
1. Wait for the CI to upload changes to the Chef Server.
1. Execute the chatops command in the `#production` channel:

    ```
    /runner run start private green
    ```

    This will enable and execute `chef-client` on the `green` deployment to install `17.7.0~pre.103.g896916a8-1` and start the `gitlab-runner` service
1. Wait for new deployments to start executing jobs, monitor in Kibana's [Runner index](https://log.gprd.gitlab.net/app/r/s/PaOx8).
1. When `green` deployment is active and healthy trigger a graceful
  shutdown to the `blue` deployment to stop the `gitlab-runner` process
  and wait for all jobs to finish.

    To do this, execute the chatops command in the `#production` channel:

    ```
    /runner run stop private blue
    ```

    This will start draining the runner and deleting the machines so this command will take a while to run!
1. Continue to monitor [ci-runners::Incident Support::runner-manager](https://dashboards.gitlab.net/goto/3tnWldAHg?orgId=1) grafana dashboard.

### Deficiencies

1. Deactivated deployment instances stay around. Destroy deactivated deployment :point_right: <https://gitlab.com/gitlab-org/gitlab-runner/-/issues/36777>
1. Remove double concurrency window during deployment :point_right: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/13844>
