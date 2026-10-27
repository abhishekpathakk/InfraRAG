# Error budget weekly reporting

How to setup a weekly slack report on error budget spend to your team.

## My stage group would like to receive Slack notifications weekly on their error budget spend

You must be in an elite stage group team! 😉🙂 Thank you for shifting right and focusing on GitLab.com.

Luckily, this is easy to configure.

Step 1: Update the `teams` section in the
[`teams.yml`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/services/teams.yml)
file, with a new `team` entry or update an existing team entry, as follows:

```yaml
teams:
- name: runner
  product_stage_group: runner
  slack_error_budget_channel: alerts-ci-cd
  send_error_budget_weekly_to_slack: true
```

1. `name` is name, using alphanumeric characters only
1. `product_stage_group` should match the `group` key in <https://gitlab.com/gitlab-com/www-gitlab-com/-/blob/master/data/stages.yml>
1. The `slack_error_budget_channel` is the channel in Slack that the team would like to use for alerts (without the initial '#')  If you wish the alert to go to multiple channels, just add more than one.  Example:

```yaml
teams:
- name: pipeline_security
  product_stage_group: pipeline_security
  slack_error_budget_channel:
  - ops-section
  - g_pipeline-security
  send_error_budget_weekly_to_slack: true
```

1. `send_error_budget_weekly_to_slack` send regular error budget reports to the slack channel.

Step 2: Invite the Error Budget Report slack app to your slack channel

In the channel you have configured as slack_error_budget_channel above, type `/invite @error_budget_report`.

Step 3: Profit! Once a week, on Monday, the error budget report for the past seven days will be posted to your slack channel.

## I have questions or feature requests

This feature is owned by the Scalability team, and the best way to get our attention is to create an issue in <https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues>.
