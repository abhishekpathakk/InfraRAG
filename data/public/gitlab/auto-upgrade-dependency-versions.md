# Auto-upgrading Dependency Versions

Each cell has many dependencies. We aim to keep all of them close to the latest available version automatically. The GitLab application version is our main dependency and is upgraded during the [auto-deploy process]. For other dependencies, we use [Renovate Bot] inside [cells/tissue]. For instance, we use it to upgrade the versions of Instrumentor (`instrumentor_version`) and the pre-release [GitLab Helm chart] used by Instrumentor (`gitlab_custom_helm_chart.version`).

[[ _TOC_ ]]

## Setup

There is a `dependencies.yml` file for the `cellsdev` and `cellsprod` environments. This file is automatically updated by Renovate. There is a [`postUpgradeTask`] inside the [Renovate configuration]: First, Renovate will update the dependencies YAML file. Then, it will run the post upgrade script, which uses `ringctl` to create an MR with the appropriate patch. Upon merging this MR, the patch will update the tenant model of various cells, and using the various stages of Instrumentor, the new version of the dependency is deployed to cells progressively.

## Dependency versions source

We fetch the latest version for each dependency from a specific source. Each source has its own authentication requirements. The Renovate bot pipelines run in GitLab CI on the Ops instance of the [cells/tissue] repository. These pipelines must be configured with the appropriate tokens for authentication for this process to work.

1. `instrumentor_version`: Renovate reads the tags from the [Instrumentor repository on Ops]. The [canonical codebase for Instrumentor] is on GitLab.com, so tags are synced from GitLab.com using mirroring. Renovate uses a group level access token which gives it access to the tags of this private repository on Ops.
2. `gitlab_version`: Renovate reads the tags of the GitLab Rails CNG container image `registry.gitlab.com/gitlab-org/build/cng/gitlab-rails-ee`. This list is publicly available without authentication.
3. `gitlab_custom_helm_chart.version`: Renovate reads the tags from a [private OCI registry] hosted on Google Artifact Registry. Pre-release Helm charts are pushed to this registry as part of the [nightly build process] which is described in [Development builds]. The Renovate CI pipeline uses Vault's service account impersonation feature to read the list of available tags from Artifact registry.

## Other considerations

### Instrumentor authentication to download pre-release charts

A long-lived service account key for the read-only service account is stored in Vault, and made available to Amp CI pipelines. Whenever we deploy to a cell, this secret will be used to fetch the pre-release Helm chart version configured in the tenant model from artifact registry. Information about generating and rotating this token can be found in [this runbook](https://gitlab-com.gitlab.io/gl-infra/gitlab-dedicated/team/runbooks/artifact-registry-helm-credential.html#managing-the-artifact-registry-helm-credential-token)

### Impersonate service accounts using Vault

In order to allow Renovate to contact a private artifact registry, we use the Vault [Impersonated accounts] feature and [allow the Vault SA] to impersonate an SA that can read artifact registry.

### Pre-release Helm chart versions

The pre-release tag `9.0.1-384015` is a combination of the next chart version (`9.0.1`) and the build pipeline in which the artifact was built (`384015`)

This pipeline ID is for the Charts repository mirror on the [dev.gitlab.org] instance:

```
https://dev.gitlab.org/gitlab/charts/gitlab/-/pipelines/384015
```

### Use `loose` instead of `semver` for pre-release versions

The pre-release Helm chart versions pushed to artifact registry look like this:

- 8.10.1-375113
- 8.10.1-376000
- 8.10.1-375151
- 8.11.1-379213
- 9.0.1-384015

According to semver, `8.10.1-375113` is a pre-release version that comes before 8.10.1. So, the logical upgrade path according to semver is `8.10.1-375113` => `8.10.1-376000` => `8.10.1` => `8.11.1-379213` => `8.11.1` => `9.0.1-384015` => `9.0.1` => so on. However, in the OCI registry that stores the pre-release chart `us-east1-docker.pkg.dev/gitlab-com-artifact-registry/gitlab-devel-chart/gitlab`, we don't store the tagged releases. We store only pre-release Helm charts. So, Renovate refuses to go beyond `8.10.1-376000` because it can not find the next stable version `8.10.1`. Using `loose` instead of `semver` as the `versioningTemplate` works around this behavior.

[Renovate Bot]: https://github.com/renovatebot/renovate
[cells/tissue]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/
[GitLab Helm chart]: https://gitlab.com/gitlab-org/charts/gitlab
[`postUpgradeTask`]: https://docs.renovatebot.com/configuration-options/#postupgradetasks
[Renovate configuration]: https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/blob/327c181581925c6f84b511c72c2188a225b578f5/renovate.json
[Instrumentor repository on Ops]: https://ops.gitlab.net/gitlab-com/gl-infra/gitlab-dedicated/instrumentor/-/tags
[canonical codebase for Instrumentor]: https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/instrumentor
[nightly build process]: https://gitlab.com/gitlab-org/charts/gitlab/-/blob/5613c3aaf1cacdc6df7e05b96de980be74742116/.gitlab-ci.yml#L563-573
[Impersonated accounts]: ../vault/usage.md#impersonated-accounts
[allow the Vault SA]: https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/11171
[auto-deploy process]: https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/cells/infrastructure/deployments/#todays-process
[Development builds]: https://gitlab.com/gitlab-org/charts/gitlab/-/blob/master/doc/development/release.md#development-builds
[dev.gitlab.org]: https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production/architecture/supporting-architecture/#dev-gitlab-org
[private OCI registry]: https://console.cloud.google.com/artifacts/docker/gitlab-com-artifact-registry/us-east1/gitlab-devel-chart/gitlab?inv=1&invt=Ab03dg&project=gitlab-com-artifact-registry
