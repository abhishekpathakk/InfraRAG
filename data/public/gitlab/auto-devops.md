# Auto DevOps

[Auto DevOps](https://docs.gitlab.com/topics/autodevops/) is a reusable CI/CD
configuration.  Auto DevOps can be used [in place of a
`.gitlab-ci.yml`](https://docs.gitlab.com/topics/autodevops/#enable-or-disable-auto-devops),
or as an [addition to an existing
`.gitlab-ci.yml`](https://docs.gitlab.com/ci/yaml/#includetemplate).

Auto DevOps bugs typically cause pipeline failures, but, in extreme cases, can also
result in broken user applications.

Auto DevOps is
[vendored](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Auto-DevOps.gitlab-ci.yml)
together with the GitLab Rails application code. Fixes to Auto DevOps
configuration always require a full rollout of the GitLab Rails application.
But in the interim, bad image updates to Auto Build and Auto Deploy can be
temporarily overridden using instance level CI/CD variables.

## Quickly mitigate a bad update to Auto Build or Auto Deploy images

A bad image update can be reverted without a full rollout of the Rails
application code, by setting instance-level CI/CD variables.

### Symptoms

* Numerous reports of failing Auto Build jobs following an update to `AUTO_BUILD_IMAGE_VERSION`
* Numerous reports of failing Auto Deploy jobs following an update to `AUTO_DEPLOY_IMAGE_VERSION` or `DAST_AUTO_DEPLOY_IMAGE_VERSION`

### Pre-checks

* Verify that the affected component has been recently updated
* Reproduce the problem or otherwise confirm it. If in doubt, contact [`#f_autodevops` on Slack](https://gitlab.enterprise.slack.com/archives/CAP6K884U) (internal link) for help.

### Resolution

1. Identify a good image version:
    * `AUTO_DEPLOY_IMAGE_VERSION` and `DAST_AUTO_DEPLOY_IMAGE_VERSION`:
      * If the problem was caused by an update, use the previously version in [`Jobs/Deploy.gitlab-ci.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Jobs/Deploy.gitlab-ci.yml).
      * In rare cases, a fix may need to be implemented in  [`auto-deploy-image`](https://gitlab.com/gitlab-org/cluster-integration/auto-deploy-image). For example, if a hardcoded remote goes permanently offline, then every released version will be equally broken.
    * `AUTO_BUILD_IMAGE_VERSION`:
      * If the problem was caused by an update, use the previously used version in [`Jobs/Build.gitlab-ci.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Jobs/Build.gitlab-ci.yml).
      * In rare cases, a fix may need to be implemented in [`auto-build-image`](https://gitlab.com/gitlab-org/cluster-integration/auto-build-image) (e.g. hardcoded remote going offline).
1. Set instance CI/CD variables to override the default versions of the affected image.
    * Navigate to [instance level CI/CD settings](https://gitlab.com/admin/application_settings/ci_cd) and expand the **Variables** section.
    * The version overrides should **not be protected**, and **not be masked**
    * For Auto Deploy, set `AUTO_DEPLOY_IMAGE_VERSION` _and_ `DAST_AUTO_DEPLOY_IMAGE_VERSION` to the chosen version
    * For Auto Build, set `AUTO_BUILD_IMAGE_VERSION` to the chosen version
1. Open an MR against the CI/CD template with the fix
    * For Auto Deploy:
       * Update `AUTO_DEPLOY_IMAGE_VERSION` in [`Jobs/Deploy.gitlab-ci.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Jobs/Deploy.gitlab-ci.yml)
       * Update `DAST_AUTO_DEPLOY_IMAGE_VERSION` in [`Jobs/DAST-Default-Branch-Deploy.gitlab-ci.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Jobs/DAST-Default-Branch-Deploy.gitlab-ci.yml)
    * For Auto Build:
       * Update `AUTO_BUILD_IMAGE_VERSION` in [`Jobs/Build.gitlab-ci.yml`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/gitlab/ci/templates/Jobs/Build.gitlab-ci.yml)
1. Once updated code fully rolled out to gprd, unset the CI/CD variables.
    * Navigate to [instance level CI/CD settings](https://gitlab.com/admin/application_settings/ci_cd) and expand the **Variables** section.
    * For Auto Deploy, remove `AUTO_DEPLOY_IMAGE_VERSION` _and_ `DAST_AUTO_DEPLOY_IMAGE_VERSION`
    * For Auto Build, remove `AUTO_BUILD_IMAGE_VERSION`

### Post-checks

* If you were able to reproduce the problem, you should be able to reproduce the fix
* Double check that the overrides have been removed from the **Variables** section in thethe override has
[instance level CI/CD settings](https://gitlab.com/admin/application_settings/ci_cd)

### Rollback

* Remove your overrides from the **Variables** section of the [instance level CI/CD settings](https://gitlab.com/admin/application_settings/ci_cd)
* Revert any code changes
