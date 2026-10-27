# GitalyFileServerDown

## Overview

This alert indicates that the Gitaly file server is down. It's considered a high-severity issue that requires immediate attention. Every user with a project on the Gitaly server may be unable to use GitLab.com.

## Services

- [Service Overview](../README.md)
- Owner: [Gitaly Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)
- **Label**: gitlab-com/gl-infra/production~"Service::Gitaly"

## Metrics

The [GitalyFileServerDown alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L81) is monitoring the status of the Gitaly service on a node and triggers an alert if the service has been down for more than 15 minutes

## Alert Behavior

- This alert should be rare, but if it's triggered, needs to be investigated immediately

## Severities

- This alert might create S1 incidents.
- There might be some gitlab.com users impact
- Review [Incident Severity Handbook](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/#incident-severity) page to identify the required Severity Level

## Verification

- [Mimir Gitaly instances status in gprd environment](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22yah%22:%7B%22datasource%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22up%7Bjob%3D%5C%22scrapeConfig%2Fmonitoring%2Fprometheus-agent-gitaly%5C%22,tier%3D%5C%22stor%5C%22,type%3D%5C%22gitaly%5C%22,env%3D%5C%22gprd%5C%22%7D%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Current alerts for Gitaly file servers](https://alerts.gitlab.net/#/alerts?filter=%7Btype%3D%22gitaly%22%2C%20tier%3D%22stor%22%7D)

## Recent changes

- [Closed production issues for Gitaly Service](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AGitaly&first_page_size=100)

## Troubleshooting

- [Basic troubleshooting steps](../gitaly-down.md)
- [Additional logs to check](../gitaly-down.md#2-check-the-gitaly-logs)
- [Check if the gitaly process is running and prometheus is responding to requests](../gitaly-down.md#3-ensure-that-the-gitaly-server-process-is-running)

## Possible Resolutions

- [Past GitalyFileServerDown incidents](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=closed&label_name%5B%5D=Service%3A%3AGitaly&label_name%5B%5D=incident&label_name%5B%5D=a%3AGitalyFileServerDown&first_page_size=100)

## Dependencies

There is no external dependency for this alert

## Escalation

For escalation contact the following channels:

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)

Alternative slack channels:

- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)
- [#infrastructure_platforms](https://gitlab.enterprise.slack.com/archives/C02D1HQRTKQ)

## Definitions

- [GitalyFileServerDown alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L81)
- [Edit this playbook](GitalyFileServerDown.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related alerts](./)
- [Gitaly Runbook docs](../README.md)
- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L81)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
