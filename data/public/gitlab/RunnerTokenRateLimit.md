# RunnerTokenRateLimit

This page covers two alerts about the per-token job request limit:

* `RunnerTokenRateLimitedOnJobRouter`: GitLab is rate limiting a token's job requests on the Job Router path.
* `RunnerTokenRateLimitedOnDirectPath`: GitLab is rate limiting a token's job requests on the direct path.

## Overview

Rails limits job requests per runner token. The setting is `runner_jobs_request_api_limit`, 2,000 requests per minute by default, which is about 33 per second in a fixed one-minute window. The rule is `limit_runner_job_requests_by_runner_token`.

On GitLab.com every manager of an instance runner shard shares one token, and a busy shard sends more job requests than the limit allows. GitLab-operated managers are therefore exempt. HAProxy main sets the rate-limit bypass header for requests whose source is one of the manager NAT subnets of the [Private Service Connect paths](../ci-runner-networking.md#private-service-connect-for-runner-manager-traffic):

* On the direct path the request arrives from the manager's NAT address and matches the rule directly.
* On the Job Router path the request arrives from Relay. Relay forwards the manager's address as `GitLab-Real-IP`, HAProxy adopts it as the source for connections from the KAS pod ranges, and the same rule matches.

Self-managed runners that use the Job Router arrive with their own address and keep their limit. These alerts only see our fleet, so when one fires the exemption chain is broken somewhere.

When the limit applies, the shard cannot pick up more than about 33 jobs per second no matter how many executors are idle. Jobs queue for as long as demand stays above the cap. In [INC-14709](https://app.incident.io/gitlab/incidents/14709) the `saas-linux-small-amd64` shard sat at the cap for five hours, queue p95 reached 14.6 minutes, and the apdex alert fired four and a half hours after the cap started. These alerts exist so the cap is seen in minutes.

## Services

* [ci-runners](../README.md): the runner managers that send the requests and expose the metrics.
* [Relay (kas)](../../kas/job-router.md): the Job Router path. Its rate limiting section describes how a 429 reaches the runner.
* Rails: owns the limit and the bypass header.
* HAProxy main: sets the bypass header and adopts the forwarded address. The [networking page](../ci-runner-networking.md#private-service-connect-for-runner-manager-traffic) has the details.

## Metrics

* `gitlab_runner_job_router_get_job_requests_total{code="ResourceExhausted"}`: job requests through the router that Rails answered with 429.
* `gitlab_runner_api_request_attempts_total{endpoint="request_job", status="429"}`: job requests on the direct path that Rails answered with 429, counted per attempt.
* `gitlab_labkit_rate_limiter_rule_evaluations_total{rule="limit_runner_job_requests_by_runner_token", result="block"}`: the Rails side of the same events.

The `runner` label on the runner metrics is the short token. The `shard` label names the shard.

## Alert Behavior

* Both alerts fire when a token sees more than 0.5 limited requests per second for 10 minutes. They are grouped by shard and token.
* Both route to the Runners Platform alert channel, `#g_runners_platform_alerts`, like the other runner manager alerts.

## Severities

Both are S3. Job pickup for the shard is capped while they fire. Expect the queue for the shard to grow and the [ci-runners apdex](CiRunnersServiceCiRunnerJobsApdexSLOViolationSingleShard.md) to follow hours later.

## Verification

1. Confirm Rails is blocking the token. In Grafana against the gprd Mimir tenant:

   ```promql
   sum by (result) (rate(gitlab_labkit_rate_limiter_rule_evaluations_total{env="gprd", rule="limit_runner_job_requests_by_runner_token"}[5m]))
   ```

   `result="block"` rising at the same time as the alert confirms it.
2. Find where the requests reach Rails from. In Kibana, `json.remote_ip` on the Rails API log for the shard's job requests should be an address from the manager NAT subnet on the direct path, and from the Relay NAT subnet on the Job Router endpoint, `/api/:version/internal/ci/job_router/jobs/request`. The [Job Router runbook](../../kas/job-router.md#logs) has the query, the networking page the subnets. A KAS pod address on the Job Router endpoint means the forwarded address was not adopted. A manager pod address, a Cloud NAT address or an address outside the NAT subnets means the shard is not on PSC.
3. Check the effect on the shard. Job pickup flat at about 33 per second with idle executors is the cap. Managers log `Checking for jobs... rate limited` with `retry_after` in `pubsub-runner-inf-gprd-*`.

## Recent changes

* A shard changed its path: `api_url` or `job_router_url` emptied or changed in [argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&search=gitlab-runner), or a new shard whose `url` is not `ci-gateway`.
* A change to the HAProxy main bypass rule or to its trusted real-IP sources: the `<env>-base-haproxy-main-config` role in [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo), the `main-internal-http` values in argocd/apps for gstg.
* A Relay deploy. Relay forwards the manager's address on every Job Router call, so a regression there removes the exemption on the router path only.
* A change to `runner_jobs_request_api_limit`.

## Troubleshooting

* Rate limited on the Job Router path: the job requests reach Rails without the manager's address. Either Relay stopped forwarding `GitLab-Real-IP`, HAProxy no longer adopts it for the KAS pod ranges, or the Relay NAT subnet is missing from the bypass rule. The `json.remote_ip` check above tells which. In Rails logs an exempt request has `throttle_safelist: throttle_bypass_header`.
* Rate limited on the direct path: the requests do not arrive from a manager NAT subnet. Check the shard's `api_url` and the manager's egress address against the networking page.

## Possible Resolutions

* Restore the chain rather than working around it: fix the values file, the HAProxy role, or roll back the Relay deploy that broke forwarding.
* Stopgap on either path: raise `runner_jobs_request_api_limit`. It is an application setting and needs no deploy, but it applies to every customer token too, so it needs a change request and should be reverted once the chain is fixed.
* Do not add more tokens to spread the load. After [INC-14098](https://app.incident.io/gitlab/incidents/14098) we decided to keep one token per shard and rely on the bypass.

## Dependencies

* Rails rate limiting, `Gitlab::ApplicationRateLimiter`, and the `GITLAB_THROTTLE_BYPASS_HEADER` setting that makes the bypass header work.
* HAProxy main, which sets the header for the manager NAT subnets and adopts `GitLab-Real-IP` from the KAS pod ranges.
* Relay, which forwards the manager's address on every Job Router call.
* The PSC endpoints and NAT subnets described on the networking page.

## Escalation

Runners Platform runs the managers and their network path, and owns these alerts. Reach them in `#g_runners_platform`. Runner Core owns Relay's forwarding of the manager address and the Rails limit. Reach them in `#g_runner_core`. The HAProxy owner is in the [Job Router runbook](../../kas/job-router.md#where-each-piece-runs-on-gitlabcom).

## Definitions

* The rules are in `libsonnet/alerts/runner-manager-alerts.libsonnet`. Regenerate with `./scripts/generate-jsonnet-rules.sh mimir-rules-jsonnet/runners-platform-alerts.jsonnet`.
* Tune the thresholds there: 0.5 limited requests per second and 10 minutes.

## Related Links

* [gitlab#631513](https://gitlab.com/gitlab-org/gitlab/-/work_items/631513): the per-token limit on the Job Router path and how the exemption was extended to it.
* [gitlab-runner#39944](https://gitlab.com/gitlab-org/gitlab-runner/-/work_items/39944): the Private Service Connect paths and their rollout.
* [gitlab-runner#39391](https://gitlab.com/gitlab-org/gitlab-runner/-/work_items/39391): Job Router alerts.
* [INC-14709](https://app.incident.io/gitlab/incidents/14709) and [INC-14098](https://app.incident.io/gitlab/incidents/14098).
* [Job Router runbook](../../kas/job-router.md).
