# (Title: Name of alert)

## Overview

- > What does this alert mean?
- > What factors can contribute?
- > What parts of the service are effected?
- > What action is the recipient of this alert expected to take when it fires?

## Services

- > All alerts require one or more Service Overview links
- > Team that owns the service

## Metrics

- > Briefly explain the metric this alert is based on and link to the metrics catalogue. What unit is it measured in? (e.g., CPU usage in percentage, request latency in milliseconds)
- > Explain the reasoning behind the chosen threshold value for triggering the alert. Is it based on historical data, best practices, or capacity planning?
- > Describe the expected behavior of the metric under normal conditions. This helps identify situations where the alert might be falsely firing.
- > Add screenshots of what a dashboard will look like when this alert is firing and when it recovers
- > Are there any specific visuals or messages one should look for in the screenshots?

## Alert Behavior

- > Information on silencing the alert (if applicable). When and how can silencing be used? Are there automated silencing rules?
- > Expected frequency of the alert. Is it a high-volume alert or expected to be rare?
- > Show historical trends of the alert firing e.g  Kibana dashboard

## Severities

- > Guidance for assigning incident severity to this alert
- > Who is likely to be impacted by this cause of this alert?
  - > All gitlab.com customers or a subset?
  - > Internal customers only?
- > Things to check to determine severity

## Verification

- > Prometheus link to query that triggered the alert
- > Additional monitoring dashboards
- > Link to log queries if applicable

## Recent changes

- > Links to queries for recent related production change requests
- > Links to queries for recent cookbook or helm MR's
- > How to properly roll back changes

## Troubleshooting

- > Basic troubleshooting order
- > Additional dashboards to check
- > Useful scripts or commands

## Possible Resolutions

- > Links to past incidents where this alert helped identify an issue with clear resolutions

## Dependencies

- > Internal and external dependencies which could potentially cause this alert

## Escalation

- > How and when to escalate
- > Slack channels where help is likely to be found:

## Definitions

- > Link to the definition of this alert for review and tuning
- > Advice or limitations on how we should or shouldn't tune the alert
- > Link to edit this playbook
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- > `[Related alerts](./)` Link to this /alert/ directory
- > Related documentation
