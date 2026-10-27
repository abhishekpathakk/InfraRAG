# High build pressure

## Background

Build pressure is the number of commits that are yet to be included in a version. Only projects whose versions
are bumped by release-tools are considered for this alert. In other projects, bumping of the version is handled
by the corresponding teams. The projects whose commits are counted towards this alert are Omnibus, CNG, GitLab,
Gitaly and KAS.

When build pressure is high, it indicates that something is wrong with the process for creating new
auto-deploy packages.

## Troubleshooting

Listed here are some of the common causes for high build pressure.

1. Pipelines on master are failing.

   The build process looks for a commit with a passing pipeline, so if pipelines on
   are failing, the build process cannot continue since there are no eligible commits.

   Check the latest run of the `auto_deploy: Create new package` scheduled pipeline in
   <https://ops.gitlab.net/gitlab-org/release/tools/-/pipeline_schedules>. If there are no
   eligible commits, the CI job logs will reflect that.

   If you suspect that master pipelines are broken, check the pipelines on the following projects:
   - [Omnibus](https://gitlab.com/gitlab-org/security/omnibus-gitlab/-/commits/)
   - [CNG](https://gitlab.com/gitlab-org/security/charts/components/images/-/commits/)
   - [GitLab](https://gitlab.com/gitlab-org/security/gitlab/-/commits/)
   - [Gitaly](https://gitlab.com/gitlab-org/security/gitaly/-/commits/)
   - [KAS](https://gitlab.com/gitlab-org/security/cluster-integration/gitlab-agent/-/commits/)

1. New packages are not being created

   - Check when the latest package was created by looking at the commit time of the latest commit in
     <https://ops.gitlab.net/gitlab-org/release/metadata/-/commits/master>.

   - Check the `AUTO_DEPLOY_SCHEDULE` variable in <https://ops.gitlab.net/gitlab-org/release/tools/-/settings/ci_cd#js-cicd-variables-settings>.
     It lists the hours (in UTC) in the day when new packages are to be created.

   - Based on the above two pieces of information, determine if there should have been a newer package available.

## Known situations

If the build process is blocked for a known reason, and the high build pressure is expected,
the alert can be silenced ([How to silence alerts](../monitoring/alerts_manual.md#silencing)).
