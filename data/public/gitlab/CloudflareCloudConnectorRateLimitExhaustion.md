# CloudflareCloudConnectorRateLimitExhaustion

**Table of Contents**

[TOC]

## Ownership

This alert is owned by the [Runway Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/gitlab-delivery/runway/).

## Overview

See [rate limiting](../cloudflare.md#rate-limiting) for a general description of how we enforce
rate limits in Cloudflare.

This alert fires when Cloudflare enforced rate limits that resulted in clients being blocked
for an extended period of time.

This could be for good or bad reasons:

- Good: malicious traffic from 3rd parties we have no business relationship with
- Bad: traffic from paying customers who have outgrown their rate limit budget

The "bad" case can happen when actual usage of Cloud Connector powered features outgrows
rate limits we allocate to this customer based on the number of user seats they purchased from us.

## Metrics

The alert fires when the `cloudflare_zone_firewall_events_count` rate exceeds a given threshold for
a given time window.

- [Current alerts](https://dashboards.gitlab.net/alerting/Mimir%20-%20Gitlab%20Ops/CloudflareCloudConnectorRateLimitExhaustion/find)
- [alert definition](../../../mimir-rules/gitlab-ops/cloudflare/cloudflare.yml)

## Alert Behavior

The alert does not invoke pagers but is posted to the [#cloud-connector-events](https://gitlab.enterprise.slack.com/archives/C07HJFFS2RJ) Slack channel instead.

## Troubleshooting

Cross-check in Cloudflare who was affected by these events:

- [Cloudflare: Security analytics](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/cloud.gitlab.com/security/analytics?mitigation-service=ratelimit&time-window=30)
- [Cloudflare: Security events](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/cloud.gitlab.com/security/events?service=ratelimit&time-window=30)

If you suspect it was a paying customer, refer to [possible resolutions](#possible-resolutions) for next steps. Otherwise it can be ignored.

## Possible resolutions

This is most likely only relevant in case one of the Duo-specific rate limits was exhausted.

If you established that this is affecting a paying customer whose Cloud Connector features may now be degraded,
escalate the issue with [#g_cloud_connector](https://gitlab.enterprise.slack.com/archives/CGN8BUCKC). Depending
on who the customer is and which features they use, further escalation to stage groups may be necessary.

If rate limits need to be adjusted, they can only be so for the entire rate limit bucket the customer falls into.
This means increasing rate limits will affect all other customers falling into the
same rate limit bucket too and means we need to consider increasing any limits upstream of cloud.gitlab.com
such as AI vendor quotas. Refer to [the AI gateway runbook](../../ai-gateway/README.md#gcp-quotas) in this case.

Cloudflare rate limit buckets are defined [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/cloud-connect-prd/rules.tf).
