# GitalyRequestsDropped

## Overview

Gitaly is dropping incoming requests on a node because its concurrency queue is
full. When the per-RPC concurrency limiter (or the adaptive limiter) has reached
its maximum queue size, new requests are rejected immediately with
`GRPC::ResourceExhausted`. This is measured by the
`gitaly_requests_dropped_total` counter.

When a request is dropped, user-facing errors will be triggered.

## Services

- [Service
  Overview](../README.md)
- Team that owns the service: [Tenant Scale:Gitaly
  Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)

## Metrics

The alert uses the following query which looks for dropped requests:

```promql
sum by (fqdn, reason) (rate(gitaly_requests_dropped_total{env="gprd", fqdn="<gitaly-node-here>"}[5m]))
```

- The alert fires when `rate(gitaly_requests_dropped_total[5m]) > 0` for 5
  minutes on any node.

## Alert Behavior

- Under normal conditions this metric is zero. Any sustained non-zero rate means
  requests are actively being dropped.

## Severities

- Currently configured as **s3** to allow a period of monitoring and tuning
  before upgrading to **s2**.
- Dropped requests indicate active user impact and can escalate into a wider
  incident.

## Verification

- [Gitaly Service Overview
  dashboard](https://dashboards.gitlab.net/d/gitaly-main/gitaly-overview?orgId=1)
- [Gitaly host detail
  dashboard](https://dashboards.gitlab.net/d/gitaly-host-detail/gitaly-host-detail?orgId=1)
  - See the "gitaly per-RPC metrics" and "Adaptive limit metrics" panels.
- Identify the affected nodes from the `fqdn` label and the affected RPCs from
  `grpc_method`.
- Check node saturation (CPU, memory, disk) on the affected node.
- Check whether a single repository or traffic source is driving the load, using
  Elasticsearch.
- Review whether the adaptive limiter is backing off (see
  [GitalyAdaptiveLimiterBackoff](GitalyAdaptiveLimiterBackoff.md)), which
  usually precedes dropped requests.

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
