# High deploy pressure

## Background

Deploy pressure is the number of commits that are yet to be deployed.

Staging-canary (`gstg-cny`) is the first environment that the deployment pipeline deploys a package to.
When deploy pressure on `gstg-cny` is high, it indicates that something is wrong with deployment pipelines.

## Troubleshooting

Listed here are some of the common causes for high deploy pressure on `gstg-cny`.

1. New packages are not being created

   - Check when the latest package was created by looking at the commit time of the latest commit in
     <https://ops.gitlab.net/gitlab-org/release/metadata/-/commits/master>.

   - Check the `AUTO_DEPLOY_SCHEDULE` variable in <https://ops.gitlab.net/gitlab-org/release/tools/-/settings/ci_cd#js-cicd-variables-settings>.
     It lists the hours (in UTC) in the day when new packages are to be created.

   - Based on the above two pieces of information, determine if there should have been a newer package available.

1. New deployment pipelines are not being created

   - Check when was the last deployment pipeline created by looking at deployment pipelines in
   <https://ops.gitlab.net/gitlab-org/release/tools/-/pipelines?page=1&scope=all&username=gitlab-release-tools-bot&source=api>.

   - Are there newer packages that have completed building and can be deployed?

   - New deployment pipelines should be automatically created when the latest pipeline completes deploying to `gprd-cny`
     and there are new packages that have completed building.

1. Deployments to gstg-cny are failing

   - Check the latest deployments to `gstg-cny`.

## Known situations

If deploys are blocked for a known reason, and the high deploy pressure on `gstg-cny` is expected,
the alert can be silenced ([How to silence alerts](../monitoring/alerts_manual.md#silencing)).

For planned PCLs or other times when deployments are planned to be blocked, the alert can be silenced in advance to
prevent unnecessary notifications.
