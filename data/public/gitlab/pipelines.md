# Using [`ringctl`] operations in pipelines

This document explains how to perform [`ringctl`] operations using pipelines, which serves as an alternative to running `ringctl` without having to set up the CLI locally. This can be particularly useful for anyone onboarding on to the Delivery Team or team members that do not have the latest version of the CLI set up locally.

> [Want to work with `ringctl` locally instead?](https://gitlab.com/gitlab-com/gl-infra/ringctl/-/blob/main/README.md)

## Where to execute the pipelines

The pipelines are to be executed from the [Tissue] repository on `ops.gitlab.net`. Check out the [pipelines creation interface] to get started right away.

## Patching

Learn more about patching [here](./patching/index.md).

### Available operations

Most basic operations available in the `ringctl` CLI can be executed from the pipeline. Please note that this pipeline exclusively uses [inputs] and that [variables] can't be used to execute any `ringctl` operation.

| Operation | Required arguments | Other arguments |
| -- | -- | -- |
| `get` | `patch_id` | `amp_environment` |
| `ls` | N/A | `amp_environment` |
| `retry` | `patch_id` | `amp_environment`, `dry_run` |
| `invert` | `patch_id` | `amp_environment`, `priority`, `dry_run` |
| `delete` | `patch_id` | `amp_environment`, `dry_run` |

### Ways to execute those pipelines

It is possible to declare a pipeline using the [pipelines creation interface]. Automation can be used as
well and inputs can be passed in via the [Trigger pipelines API](https://docs.gitlab.com/ci/triggers/#pass-pipeline-inputs-in-the-api-call). Here's a small example:

```curl
curl --request POST \
     --form token=TOKEN \
     --form ref=main \
     --form "inputs[ringctl_operation]=ls" \
     "https://ops.gitlab.net/api/v4/projects/793/trigger/pipeline"
```

This will execute `ringctl patch ls -e cellsdev` on the [Tissue] repository.

[`ringctl`]: https://gitlab.com/gitlab-com/gl-infra/ringctl
[Tissue]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue
[pipelines creation interface]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/pipelines/new
[inputs]: https://docs.gitlab.com/ci/inputs/
[variables]: https://docs.gitlab.com/ci/variables/
