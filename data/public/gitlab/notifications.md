# Patching Notifications

TOC

## patching-notifier

The [patching-notifier](https://gitlab.com/gitlab-com/gl-infra/ops-team/toolkit/patching-notifier) project is responsible for generating GitLab issues for security problems that are detected across our infrastructure. See the project's [README](https://gitlab.com/gitlab-com/gl-infra/ops-team/toolkit/patching-notifier/-/blob/main/README.md) for a more detailed overview of it's configuration and intended operation.

### Pipelines

There are two [scheduled pipelines](https://ops.gitlab.net/gitlab-com/gl-infra/ops-team/toolkit/patching-notifier/-/pipeline_schedules) on ops.gitlab.net that are executed regularly to perform the primary functions of patching-notifier.

- `refresh_cache` is responsible for downloading all security vulnerability information from Wiz, and saving the results to disk in JSON format. This JSON file is cached by GitLab, and shared with all other pipelines. This job runs every 6 hours and is intended to prevent us from hitting Wiz's rate limits.
- `run` is responsible for executing the `patch-notification` command within patching-notifier. This pipeline runs parallel jobs for each [configured service](https://gitlab.com/gitlab-com/gl-infra/ops-team/toolkit/patching-notifier/-/blob/59e6cbf25b2c171392e4cb3d28d181389a421fb7/.gitlab-ci.yml#L87-96) to generate GitLab issues. This pipeline executes every hour, and will use the Wiz cache generated from the `refresh_cache` job if present. **Note**: If the Wiz cache isn't present, the `patch-notification` command will automatically try to download all vulnerability information from Wiz, this may result in rate limits being hit.

### Adding a service

The general steps to follow when adding a service are:

- Ensure the `Service::` namespaced label is present under the [gl-infra](https://gitlab.com/groups/gitlab-com/gl-infra/-/labels) GitLab group. If this isn't done, patching-notifier won't be able to tell when it has already created an issue for a given service, resulting in spam issue creation.
- Add service configuration as described in the project's README, the configuration lives in `configs/service-config.yml`.
  - When setting `label`, this refers to the `Service::` label that was created, omitting the label namespace.
  - When jobs execute, service-config.yml is downloaded directly from the main branch of the repository. This means that we do not need to rebuild the container image and cut a new release for service additions or modifications.
- Add the name of the new service to the job matrix list in `.gitlab-ci.yaml`.
