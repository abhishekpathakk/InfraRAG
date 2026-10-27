# glab Runbook

## About us

- **Handbook**: [Create:Code Review Group](https://handbook.gitlab.com/handbook/engineering/devops/create/code-review/)
- **Slack channels**:
  - [#g_create_code-review](https://gitlab.enterprise.slack.com/archives/C01EMBKS5DW)
  - [#f_cli](https://gitlab.enterprise.slack.com/archives/C0380FL4K1R)
  - [#g_create_code-review_alerts](https://gitlab.enterprise.slack.com/archives/C082E78PJJK)

Create:Code Review Group is responsible for the GitLab CLI. List of features can be found in this
[handbook page](https://handbook.gitlab.com/handbook/product/categories/features/#code-review).

## Services used

GitLab CLI is a command line tool (`glab`) that interacts with the GitLab public API. It can be pointed to GitLab.com or a specific self-managed instance.

- [GitLab CLI README](https://gitlab.com/gitlab-org/cli/-/blob/main/README.md)
- [GitLab CLI usage instructions](https://gitlab.com/gitlab-org/cli/-/blob/main/docs/source/index.md)

## Dashboards and links

### Kibana

- [Logs of failed requests from GitLab CLI](https://log.gprd.gitlab.net/app/r/s/fbznK)

These logs show all failed Rails requests and jobs. They can be filtered by:

- Specific action/endpoint by `json.meta.caller_id`
- Specific job class by `json.class`
- By correlation ID by `json.correlation_id`

### GitLab CLI changelog

Information about changes made on each GitLab CLI release can be found in the project [releases page](https://gitlab.com/gitlab-org/cli/-/releases).

## Debugging

Refer to the [GitLab CLI playbook](https://internal.gitlab.com/handbook/engineering/tier2-oncall/playbooks/create/cli/) for debugging.
