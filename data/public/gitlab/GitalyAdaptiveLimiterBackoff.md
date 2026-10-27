# GitalyAdaptiveLimiterBackoff

## Overview

Gitaly's adaptive concurrency limiter is triggering backoff events on a node,
meaning a resource watcher has detected pressure and the limiter is cutting its
effective concurrency limit. This is measured by the
`gitaly_concurrency_limiting_backoff_events_total` counter, broken down by the
`watcher` that triggered the backoff.

Backoff events are a leading indicator and will fire before Gitaly starts
dropping requests (see [GitalyRequestsDropped](GitalyRequestsDropped.md)) and
downstream errors appear for clients. A backoff event doesn't always result in
dropped requests, especially if traffic returns to normal quickly.

## Services

- [Service
  Overview](../README.md)
- Team that owns the service: [Tenant Scale:Gitaly
  Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)

## Metrics

The alert uses the following query which looks for backoff events:

```promql
sum by (fqdn, watcher) (rate(gitaly_concurrency_limiting_backoff_events_total{env="gprd", fqdn="<gitaly-node-here>"}[5m]))
```

When a backoff event occurs, the concurrency limit for a gRPC endpoint is
reduced:

```
max(gitaly_concurrency_limiting_current_limit{env="gprd", fqdn="<gitaly-node-here>"}) by (fqdn, limit)
```

- The alert fires when
  `rate(gitaly_concurrency_limiting_backoff_events_total[5m]) > 0` for 5 minutes
  on any node.
- The `watcher` label identifies which resource watcher (e.g. CPU, memory, disk)
  triggered the backoff.

## Alert Behavior

- Under normal conditions this metric is zero. A sustained non-zero rate means
  the adaptive limiter is actively reducing concurrency in response to resource
  pressure.

## Severities

- Currently configured as **s3** as it is an early warning signal with no user
  impact yet.

## Verification

- [Gitaly host detail
  dashboard](https://dashboards.gitlab.net/d/gitaly-host-detail/gitaly-host-detail?orgId=1)
  - See the "Adaptive limit metrics" panel.
- Identify the affected nodes from the `fqdn` label and the source of pressure
  from the `watcher` label.
- Check node saturation (CPU, memory, disk) on the affected node.
- Check whether a single repository or traffic source is driving the load, using
  Elasticsearch.
- Watch for escalation to dropped requests
  ([GitalyRequestsDropped](GitalyRequestsDropped.md)).

## Escalation

Gitaly has a Tier 2 rotation. Follow the [How to
Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)
guidance to page the team.

Several Slack channels are also available:

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)
- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)
- [#infrastructure_platforms](https://gitlab.enterprise.slack.com/archives/C02D1HQRTKQ)

## Definitions

- [Alert
  definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml)
- [Update the template used to format this
  playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
