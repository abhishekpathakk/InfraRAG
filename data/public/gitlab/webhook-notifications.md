# High Number of Pending or Failed Outgoing Webhook Notifications

## Background

The Container Registry is configured to emit [webhook notifications](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/notifications.md) that are consumed by the GitLab Rails `/api/v4/container_registry_event/events` endpoint as seen in [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/values.yaml.gotmpl#L206).

These notifications are used by Rails to keep track of registry statistics and usage.
They are not critical and the delivery is on best-effort basis.

## Causes

A high number of pending or failed events is likely related to one of these possibilities:

- Networking error while sending an outgoing request to the `/api/v4/container_registry_event/events` endpoint on GitLab.com;
- Issues in the monolith itself, that prevent notifcations from being consumed.
- An application bug in the registry webhook notifications code.

## Symptoms

The [`ContainerRegistryNotificationsPendingCountTooHigh`](../../mimir-rules/gitlab-gprd/registry/registry-notifications.yml) alert will be triggered if the number of pending outgoing events count is higher than the configured threshold for a prolonged period of time.

The [`ContainerRegistryNotificationsPendingQueueGrows`](../../mimir-rules/gitlab-gprd/registry/registry-notifications.yml) alert will be triggered if the number of pending outgoing events is increasing faster than the configured threshold for a prolonged period of time.

The list of dashboard refrenced in the "Troubleshooting" section below can be used to gather insight on the system.

## Troubleshooting

We first need to identify the cause for the accumulation of pending outgoing notifications. For this, we can look at the following Grafana dashboards:

1. [`registry-notifications/webhook-notifications-detail`](https://dashboards.gitlab.net/d/registry-notifications/webhook-notifications-detail)
1. [`api-main/api-overview`](https://dashboards.gitlab.net/d/api-main/api-overview)
1. [`cloudflare-main/cloudflare-overview`](https://dashboards.gitlab.net/d/cloudflare-main/cloudflare-overview)
1. [Rails API logs](https://log.gprd.gitlab.net/app/r/s/nxwUF).

In (1), we should look at the failure and error rates, as well as the different status codes in the `Events per second (by Status Code)` panel.

In (2) and (3), we should look for potential errors at the Rails API level or any Cloudflare errors affecting the notifications delivery rate.

In (4), we can monitor the Rails API for the `/api/v4/container_registry_event/events` endpoint for clues on what could be going wrong.

In the presence of errors, we should also look at the registry access/application [logs in Kibana](https://log.gprd.gitlab.net/app/r/s/mUjiG).
This might allow us to see error details while trying to send a notification by searching for the string `error writing event`.
The same applies to Sentry, where all unknown application errors are reported.

## Resolution

In case there are no signs of relevant application/network errors, and all metrics seem to point to an inability to keep up with the demand please contact container-registry.
