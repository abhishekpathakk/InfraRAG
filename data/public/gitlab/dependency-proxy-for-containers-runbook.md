# Dependency proxy for containers runbook

## Summary

The Dependency Proxy for GitLab Container Registry acts as a local proxy for frequently accessed Docker images from Docker Hub.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha/upload/authorize`
* `v2/:group_id/dependency_proxy/containers/:image/blobs/:sha/upload`
* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag/upload/authorize`
* `v2/:group_id/dependency_proxy/containers/:image/manifests/*tag/upload`

## Observability

* [Dependency Proxy Dashboard](https://log.gprd.gitlab.net/app/r/s/dQP4i)
* [Dependency Proxy Statistics](https://log.gprd.gitlab.net/app/r/s/vAiWj)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/dependency_proxy/#troubleshooting)

## Service Changes

* [Recent MR's relating to Dependency Proxy](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?sort=merged_at_desc&state=merged&search=dependency%20proxy&first_page_size=20)
* [Docker Hub changelog](https://docs.docker.com/engine/release-notes/)
* [Docker Hub usage and limits](https://docs.docker.com/docker-hub/usage/)

## Common Operations

### Test Docker pull through proxy

`docker pull $GITLAB_HOST:$PORT/$GROUP_PATH/dependency_proxy/containers/library/alpine:latest`

## Credential Rotation

### Docker Organization Access Token (OAT) for Dependency Proxy

GitLab's Dependency Proxy uses a Docker Organization Access Token (OAT) to authenticate
pull-through requests to Docker Hub on behalf of users. This token is stored in 1Password
as **"Docker gitlabci OAT"** and is configured as a CI/CD variable (`GITLAB_DEPENDENCY_TOKEN`)
in the `gitlab-org` and `gitlab-com` groups.

If this token expires, CI pipelines across both groups will fail with authentication errors
when pulling images through the Dependency Proxy.

#### Symptoms of an expired token

* CI jobs fail with errors like `Error response from daemon: unauthorized: authentication required`
  or `GITLAB_DEPENDENCY_TOKEN fails to authenticate`
* Failures are widespread across multiple projects in `gitlab-org` and `gitlab-com`
* The [Dependency Proxy Dashboard](https://log.gprd.gitlab.net/app/r/s/dQP4i) shows a spike in errors

#### Manual rotation procedure

1. Log in to [Docker Hub](https://hub.docker.com) with the GitLab organization credentials
   (find them in 1Password under the `gitlab` org vault).
1. Navigate to **Organization Settings → Access Tokens** (or use the
   [Docker Hub OAT API](https://docs.docker.com/reference/api/hub/latest/#tag/org-access-tokens)).
1. Create a new Organization Access Token with `Public Repo Read-only` scope.
1. Copy the new token value.
1. Update the CI/CD variable `GITLAB_DEPENDENCY_TOKEN` in both:
   * `https://gitlab.com/gitlab-org` → Settings → CI/CD → Variables
   * `https://gitlab.com/gitlab-com` → Settings → CI/CD → Variables
1. Update the token value in 1Password under **"Docker gitlabci OAT"**.
1. Revoke the old OAT via the Docker Hub UI or API.
1. Verify by re-running a previously failing pipeline, or by running:

   > **Note:** You must be authenticated to `gitlab.com` before pulling through the Dependency Proxy.
   > An unauthenticated pull will fail regardless of whether the OAT rotation succeeded.

   ```shell
   docker login gitlab.com
   docker pull gitlab.com/gitlab-org/dependency_proxy/containers/library/alpine:latest
   ```

#### Automation

Automatic rotation via the Docker Hub API is tracked in
[production-engineering#28867](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/28867).
Until that is implemented, rotation must be done manually following the steps above.

#### References

* [Internal handbook: Rotating credentials](https://internal.gitlab.com/handbook/engineering/infrastructure/engineering-productivity/rotating-credentials/#gitlab-org--gitlab-com-dependency-proxy-credentials)
* [Docker Hub OAT API docs](https://docs.docker.com/reference/api/hub/latest/#tag/org-access-tokens)
* [Incident INC-9793](https://app.incident.io/gitlab/incidents/9793)

## Service Catalog

* **Service label:** `Service::Dependency Proxy`
* **Metrics catalog entry:** [`dependency_proxy` component in the `web` service](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/web.jsonnet)
* **Severity:** s3 (does not page SREs directly; alerts roll up to the `web` service)
* **Feature category:** `virtual_registry`
* **Owner team:** `group::container registry`
* **Slack:** `#g_container-registry`

## Primary Contacts

* **Primary Owner:** Container Registry team
* **Slack Channel:** `#g_container-registry` (GitLab internal)
* **Escalation:** `#production` for active incidents

## References

* [User Guide](https://docs.gitlab.com/user/packages/dependency_proxy/)
* [API Documentation](https://docs.gitlab.com/api/dependency_proxy/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/dependency_proxy)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/dependency_proxy)
* [Local setup](https://gitlab.com/gitlab-org/gitlab-development-kit/-/blob/main/doc/howto/dependency_proxy.md)
* [Authentication and authorization](https://docs.gitlab.com/development/packages/dependency_proxy/#authentication-and-authorization)
* [Workhorse for file handling](https://docs.gitlab.com/development/packages/dependency_proxy/#workhorse-for-file-handling)
