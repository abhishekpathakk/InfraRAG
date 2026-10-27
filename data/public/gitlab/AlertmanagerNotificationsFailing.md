# AlertmanagerNotificationsFailing

## Overview

- This alert means that Alertmanager is failing to send notifications to an upstream service, usually PagerDuty or Slack.
- This can be due to an upstream service downtime or temporary networking issues.
- This affects the ability for out engineer on call (EOC) to be notified and take actions on problems with the system.
- The recipient of the alert is expected to determine the cause of the notification failures, and if possible take actions to resolve the problem.

## Services

- [Service Overview](../README.md#alerting)
- Owner: [Production Engineering: Scalability Observability](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/observability/)

## Metrics

- This alert is firing when 4 non-webhook notifications or 10 webhook notifications fail over the course of 5 minutes.
- In normal circumstances, there should be no failed notifications.
- [Dashboard Link](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22ipt%22:%7B%22datasource%22:%22mimir-gitlab-ops%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22sum%20by%20%28integration%29%20%28%5Cn%20%20increase%28alertmanager_notifications_failed_total%7Benv%3D%5C%22ops%5C%22%7D%5B5m%5D%29%5Cn%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-ops%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- When looking at the dashboard, anything over 0 indicates there have been recent failures.

## Alert Behavior

- This alert can be silenced if we are aware of the issue and are working to resolve it.
- Additionally consider silencing it if the problem is upstream and cannot be resolved by us.
- This alert is low volume and is expected to be rare.

## Severities

- This alert is likely an S3.
- If this alert happens in conjunction with full metrics downtime, it is an S1.
- This is a fully internal alert, primarily affecting the EOC and alerting visibility.

## Verification

- [Prometheus Query Definition](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22ipt%22:%7B%22datasource%22:%22mimir-gitlab-ops%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22sum%20by%20%28integration%29%20%28%5Cn%20%20increase%28alertmanager_notifications_failed_total%7Benv%3D%5C%22ops%5C%22%7D%5B5m%5D%29%5Cn%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-ops%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Notificions Failing Total](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22jzh%22:%7B%22datasource%22:%22mimir-gitlab-ops%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22rate%28alertmanager_notifications_failed_total%5B10m%5D%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-ops%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)

## Recent changes

- [Recent Change Requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name%5B%5D=change)
- [Recent ArgoCD apps Merge Requests](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests)
  - Changes to Alertmanager are typically made under [`services/prometheus/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/prometheus), and the live Alertmanager configuration is in [`services/prometheus/env/ops/clusters/ops-gitlab-gke/values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/prometheus/env/ops/clusters/ops-gitlab-gke/values.yaml).

## Troubleshooting

- Check the AlertManager logs to find out why it could not send alerts.
  - In the `gitlab-ops` project of Google Cloud, open the `Workloads` section under
    the `Kubernetes Engine` section of the web console. Select the Alertmanager
    workload, named `alertmanager-gitlab-monitoring-promethe-alertmanager`. Here
    you can see details for the Alertmanager pods and select `Container logs`
    to review the logs.
  - The AlertManager pod is very quiet except for errors so it should be quickly
    obvious if it could not contact a service.
- Determine what integration is failing
  - In Prometheus, run this query: [`rate(alertmanager_notifications_failed_total[10m])`](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22jzh%22:%7B%22datasource%22:%22mimir-gitlab-ops%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22rate%28alertmanager_notifications_failed_total%5B10m%5D%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-ops%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1).
  - This will give you a breakdown of which integration is failing, and from
    which server.
  - For the slackline, you can view [the `alertManagerBridge` cloud function](https://console.cloud.google.com/functions/details/us-central1/alertManagerBridge?project=gitlab-infra-automation), [its logs](https://console.cloud.google.com/logs?service=cloudfunctions.googleapis.com&key1=alertManagerBridge&key2=us-central1&project=gitlab-infra-automation), and [code](https://gitlab.com/gitlab-com/gl-infra/slackline).
- Keep in mind that, if nothing has changed, the problem is likely to be on
  the remote side - for example, a Slack or Pagerduty issue.

## Possible Resolutions

- [2023-05-17: Alertmanager failed due to Slack service degredation](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/14404)
- [2023-02-26: Notifications Failing due to channel name change](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8464)
- [2023-01-30: Notifications failing due to template parsing errors](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8320)
- [2020-08-13: AlertmanagerNotificationsFailing incident](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/2519)

## Dependencies

- PagerDuty
- Slack
- GCP Networking

## Escalation

- If the problem persists with no known upstream cause, escalate to the Scalability-Observability team.
- #g_scalability-observability

## Definitions

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-ops/alertmanager.yml)
- This alert is unlikely to need tuning or modification, however in the past we have changed the wait time before having the alert fire when only a few webhooks failed and it recovered immediately.
- [Edit this Playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/monitoring/alerts/AlertmanagerNotificationsFailing.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related alerts](./)
- [Related Documentation](../README.md)
