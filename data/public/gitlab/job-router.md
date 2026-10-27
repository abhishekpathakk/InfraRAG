# Job Router

The Job Router is a GitLab Relay (KAS) module. Runners with it enabled request CI jobs from Relay over gRPC instead of polling Rails directly. Relay forwards each request to GitLab over HTTP and hands the response back to the runner. [Runner Core](https://handbook.gitlab.com/handbook/engineering/devops/runner/runner-core/) owns the module and its SLI. The SLI's alerts post to `#alerts-ci-cd` through `feature_category: runner_core`, and its weekly error budget report goes to `#ci-section` through `team: runner_core`. [Environments](https://handbook.gitlab.com/handbook/engineering/devops/runner/environments/) owns the Relay service it runs in. [Runners Platform](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/runners-platform/) owns the runner shards and the runner-side alerts. Pages from the SLO alerts go to the SRE on-call, as for every S2 SLO alert.

This page is the operational reference for the Job Router. The alert pages link here for anything they do not repeat:

- [`KasServiceJobRouterErrorSLOViolation`](alerts/KasServiceJobRouter.md#kasservicejobroutererrorsloviolation)
- [`KasServiceJobRouterTrafficCessation` and `KasServiceJobRouterTrafficAbsent`](alerts/KasServiceJobRouter.md#kasservicejobroutertrafficcessation-and-kasservicejobroutertrafficabsent)
- [`RunnerManagerNotRequestingJobs`](../ci-runners/alerts/RunnerManagerNotRequestingJobs.md), the runner-side alert, owned by Runners Platform

## How a job request flows

```
runner manager --gRPC GetJob--> HAProxy main (kas frontend) --> Relay --POST /api/v4/internal/ci/job_router/jobs/request--> Workhorse --> Rails
```

GitLab-operated managers reach the kas frontend as `kas-internal.<env>.gitlab.net:8150`, an internal load balancer behind a Private Service Connect endpoint in the `ci` VPC. Self-managed runners reach it as `kas.gitlab.com` through Cloudflare Spectrum. Same frontend, same Relay. The PSC side is described in [the runner networking page](../ci-runners/ci-runner-networking.md#private-service-connect-for-runner-manager-traffic).

1. The runner asks Rails where the router is with `GET /api/v4/runners/router/discovery`. Rails answers with the Relay URL, `grpcs://kas.gitlab.com`, when the `job_router` flag is on for the runner's group (or, for an instance runner, one of the instance flags), and 501 when it is not. The runner caches the answer for five minutes. A runner with `job_router_url` set still runs discovery, and still falls back on 501, but dials the configured address instead of the advertised one. Our managers set it to the PSC address.
2. The runner keeps one gRPC connection to Relay and calls `GetJob` once per poll, with the same JSON it would send to `POST /api/v4/jobs/request`.
3. Relay resolves the runner token through `GET /api/v4/internal/ci/agents/runner/info`, then forwards the job request to the internal endpoint. Workhorse treats it like the direct endpoint: with no job available it holds the request for its CI long-poll window (50 seconds) and answers 204. Relay passes the `X-GitLab-Last-Update` token back to the runner, which echoes it on the next poll, so Workhorse coalesces empty polls instead of sending them to Rails.
4. Relay maps GitLab's answer to a gRPC status code and returns the body unchanged.

Relay keeps no state for this. Any Relay pod can serve any request.

### Where each piece runs on GitLab.com

| Piece | Where | Owner |
| ------- | ------- | ------- |
| Runner managers with `FF_USE_JOB_ROUTER` | The shards whose values set `featureFlags.FF_USE_JOB_ROUTER` under `services/gitlab-runner/env/gprd-ci/shards/` in [argocd-apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps), and the chef roles that set it under `feature_flags` in [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/roles). `grep -rl FF_USE_JOB_ROUTER` in either repo lists them | Runners Platform |
| `kas.gitlab.com`, `kas-internal.gprd.gitlab.net` | The main HAProxy fleet, kas frontend on 8150. Native gRPC (HTTP/2) and WebSocket (HTTP/1.1) go to separate Relay backends. The gRPC backend is health-checked on Relay's `/readiness`. `kas-internal` is an internal load balancer on the same frontend, reached by our managers over PSC. See the [frontend runbook](../frontend/README.md) | [Networking and Incident Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/networking-and-incident-management/) |
| Relay | The `kas` deployment in the `gitlab` namespace of the regional GKE cluster, deployed from [k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com) with the GitLab auto-deploy. See [Relay basic troubleshooting](kas-basic-troubleshooting.md) | Environments |
| Internal endpoint | Workhorse route `api_job_router_jobs_request`, Rails `API::Internal::Ci::JobRouter` | Runner Core |

### The switches

| Switch | Scope | How to check |
| ------ | ----- | ------------ |
| Rails flag `job_router` | Group and project runners, by the runner's root namespace. Enabled globally it covers instance runners too | `/chatops run feature get job_router` |
| Rails flag `job_router_instance_runners` | Individual instance runners | `/chatops run feature get job_router_instance_runners` |
| Runner flag `FF_USE_JOB_ROUTER` | One shard | The shard configuration linked above |
| Runner setting `job_router_url` | Which address a routing shard dials | `shardConfig.jobRouterUrl` in the environment defaults in argocd-apps; empty in a shard's file sends that shard back to `kas.gitlab.com` |

A runner routes only when its shard flag and the Rails flag for its group are both on. Everything else polls Rails directly, as before. Flag changes are recorded in [feature-flag-log](https://gitlab.com/gitlab-com/gl-infra/feature-flag-log/-/issues/?search=job_router).

## What can go wrong

The runner is built to survive the router. When Relay is unreachable, its circuit breaker trips after three consecutive failures spanning at least 5 seconds, and the runner polls Rails directly until Relay answers again. When the Rails flag is off, Relay answers `Unimplemented` and the runner drops the router on its next poll. So a Job Router problem usually costs job pickup time rather than jobs, and the first question in an incident is: are runners falling back cleanly, and is the direct path healthy?

| Symptom | Where | Meaning | Action |
| --------- | ------- | --------- | -------- |
| `Unavailable` rising on `GetJob by Response Code` | [Job Router dashboard](https://dashboards.gitlab.net/d/kas-job-router), error SLO alert | Relay could not complete the call to GitLab. The only code the SLI counts as an error. | [Error alert](alerts/KasServiceJobRouter.md#kasservicejobroutererrorsloviolation) |
| GetJob rate at zero | Traffic cessation or absent alert | Runners stopped calling Relay: a flag went off, or runners cannot reach Relay | [Traffic alerts](alerts/KasServiceJobRouter.md#kasservicejobroutertrafficcessation-and-kasservicejobroutertrafficabsent) |
| `breaker_tripped` then `breaker_open` on `Runner-side Fallbacks/sec` across a shard, Relay-side panels blank | Runner-side row | Runners cannot reach Relay and are polling Rails directly. CI continues without the router | Check Relay pods, `kas.gitlab.com` on HAProxy, and Relay saturation. Runners resume on their own once Relay answers |
| `dial_failed` fallbacks | Runner-side row | Runners cannot open a connection: DNS, TLS, HAProxy, or a wrong URL from discovery | Read the error on the runner log line `Job router dial failed`, then check HAProxy and certificates |
| `no_discovery` fallbacks | Runner-side row | Discovery did not return a router: 501 when the Rails flag is off for that runner's group, but also 403, 5xx, or a failed request. A failed discovery is cached for five minutes | Expected after a rollback. Otherwise read the status on the runner log line `Discovering Job Router...` and check the flag |
| `router_disabled` fallbacks and `Unimplemented` on Relay | Both rows | The Rails flag is off. This is the rollback path | Expected during a rollback. Silence the traffic alerts |
| `ResourceExhausted` rising | Response code panel, runner `get_job_requests_total{code="ResourceExhausted"}` | GitLab is rate limiting job requests for that runner token. Not an SLI error, but job pickup slows | [Rate limiting](#rate-limiting) |
| `PermissionDenied`, managers disabled by the health check | Runner logs, `RunnerManagerNotRequestingJobs` | GitLab answered 403: the runner token is invalid or the runner was removed | Runner side. See the [runner manager page](../ci-runners/alerts/RunnerManagerNotRequestingJobs.md) |
| GetJob duration for `result="job"` rising | Latency panels on both rows | Rails, Workhorse, or Relay is slow on the job path | [Latency](#latency) |

## Rollback

Two switches, one on each side of the connection. Neither needs a restart.

### Rails flag: every runner, or one group

```
/chatops run feature set job_router false
/chatops run feature set --group=gitlab-org job_router false
```

Run it in `#production` and cross-post to `#g_runner_core`. Check how the flag is enabled first, with `/chatops run feature get job_router`: while it is enabled globally, disabling it for one group has no effect, and the global flag also covers instance runners, so the rollback is the global disable. While the flag is off, the internal endpoint answers 501, Relay returns `Unimplemented`, and each runner drops the router on its next poll. Discovery answers 501 as well, so runners stay on the direct path until the flag is back on.

Verify: `Unimplemented` replaces the other codes on `GetJob by Response Code`, `router_disabled` appears on `Runner-side Fallbacks/sec`, and direct `POST /api/v4/jobs/request` traffic comes back on the [incident dashboard](https://dashboards.gitlab.net/d/ci-runners-incident-gitlab-application). The traffic cessation alert will fire once the 30-minute rate has been zero for 5 minutes. Silence it with `type="kas", component="job_router"`.

To re-enable, set the flag to `true`. Runners rediscover the router when their discovery cache expires, within five minutes, or on restart.

### Runner flag: one shard

Set `FF_USE_JOB_ROUTER` to `false` in the shard's runner configuration:

- Kubernetes shards: `featureFlags.FF_USE_JOB_ROUTER` in `services/gitlab-runner/env/gprd-ci/shards/<shard>/clusters/<cluster>/values.yaml` in [argocd-apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps). ArgoCD applies the change.
- Chef shards: `cookbook-gitlab-runner.runners.<runner>.feature_flags.FF_USE_JOB_ROUTER` in the role in [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo). The next chef-client run applies it.

The runner reloads its configuration when the file changes and stops calling the router. Use this when one shard misbehaves, or to keep the Rails flag on for everyone else.

### Relay itself

A Relay regression is rolled back like any other auto-deploy component. Restarting or scaling Relay is in [Relay basic troubleshooting](kas-basic-troubleshooting.md). Runners on the direct path are unaffected by anything you do to Relay.

## Rate limiting

Rails limits job requests per runner token (`runner_jobs_request_api_limit`, 2,000 per minute by default). A shard whose managers share one token can hit it. Through the router a 429 arrives as `ResourceExhausted`.

GitLab-operated managers are exempt: HAProxy sets `X-GitLab-RateLimit-Bypass: 1` for requests whose source is the PSC NAT subnet of the manager traffic. On the Relay path that works because Relay forwards the manager's address as `GitLab-Real-IP` and HAProxy adopts it as the source for connections from the KAS pod range before setting the header. Self-managed runners using the router arrive with their own address and the limit applies to them. If a GitLab-operated shard shows `ResourceExhausted`, check that its job router calls reach Rails from `10.218.11.16/28` (`json.remote_ip` on the internal endpoint in Kibana); if they come from a KAS pod address instead, the forwarding chain is broken somewhere between Relay and the https frontend. Relay forwards GitLab's `Retry-After` and does not retry. The runner logs `Checking for jobs... rate limited`, releases its request slot, lowers its adaptive request concurrency, and polls again after `check_interval`.

Signs: `ResourceExhausted` on the response code panel, `gitlab_runner_job_router_get_job_requests_total{code="ResourceExhausted"}` rising for a shard, `gitlab_labkit_rate_limiter_rule_evaluations_total{rule="limit_runner_job_requests_by_runner_token", result="block"}` rising on Rails, and slow pickup on that shard with nothing else wrong. For a GitLab-operated shard, repair the forwarding chain above. Raising the limit is a stopgap only, and more tokens are not an option: a shard keeps one token and relies on the bypass. The alerts for it, and the steps to take, are in [RunnerTokenRateLimit](../ci-runners/alerts/RunnerTokenRateLimit.md). The issue that made this visible is [production-engineering#29774](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29774).

## Latency

There is no latency alert. One is tracked in [gitlab-runner#39391](https://gitlab.com/gitlab-org/gitlab-runner/-/work_items/39391). Use the panels:

- `GetJob Duration - GitLab returned a job`, on both rows. Only `result="job"` tells you anything, because an empty poll waits out the 50 second long-poll window by design. The Relay-side panel is what Relay controls; the runner-side panel adds the network.
- `Runner Controller Lookup Duration`: the `GET /api/v4/internal/ci/job_router/runner_controllers/job_admission` call Relay makes on every job before handing it over. It runs inline in GetJob, so it is part of every job's latency even though admission control is off on GitLab.com.
- Rails API latency and Workhorse queueing on the [API dashboard](https://dashboards.gitlab.net/d/api-main). Relay CPU, memory, and in-flight requests on the [Relay overview](https://dashboards.gitlab.net/d/kas-main).

Slow GetJob for `result="job"` with a healthy Rails points at Relay. Check saturation and recent Relay deploys, and raise `gitlab.kas.minReplicas` in k8s-workloads if the pods are full. If pickup is unacceptably slow and the cause is on the router path, roll back to direct polling.

## Observability map

### Dashboards

- [Job Router](https://dashboards.gitlab.net/d/kas-job-router): Relay-side GetJob, the runner-side view with fallbacks and circuit breakers, admission control (off on GitLab.com), and overall Relay health. Every panel description explains its codes and labels.
- [Relay overview](https://dashboards.gitlab.net/d/kas-main): the `job_router` SLI against its SLO, saturation, and the WebSocket versus gRPC transport row.
- [CI Runners: request concurrency](https://dashboards.gitlab.net/d/ci-runners-request-concurrency) and [CI Runners: incident, GitLab application](https://dashboards.gitlab.net/d/ci-runners-incident-gitlab-application) for the direct path and Workhorse polling.

### Metrics

| Side | Metric | Tells you |
| ------ | -------- | ----------- |
| Relay | `grpc_server_handled_total{grpc_service="gitlab.agent.job_router.rpc.JobRouter"}` by `grpc_code` | Request and error rate. The SLI |
| Relay | `job_router_get_job_duration_seconds{result}` | Latency by outcome: `job`, `no_job`, `error`, `rate_limited` |
| Relay | `grpc_server_requests_in_flight{grpc_service="gitlab.agent.job_router.rpc.JobRouter"}` | Held polls |
| Runner | `gitlab_runner_job_router_fallbacks_total{reason}` | Why requests bypassed the router |
| Runner | `gitlab_runner_job_router_circuit_breaker_state`, `gitlab_runner_job_router_circuit_breaker_trips_total` | 0 closed, 1 open, 2 half-open |
| Runner | `gitlab_runner_job_router_get_job_duration_seconds{runner,system_id,result}` | Round trip per shard and outcome |
| Runner | `gitlab_runner_job_router_get_job_requests_total{runner,system_id,code}` | Every GetJob by gRPC code (Runner 19.5 and later) |
| Runner | `gitlab_runner_job_router_discovery_cache_events_total{result}` | Discovery hits and misses |
| Workhorse | `gitlab_workhorse_http_requests_total{route_id="api_job_router_jobs_request"}` by `code` | The internal endpoint as Workhorse sees it |
| Rails | `gitlab_labkit_rate_limiter_rule_evaluations_total{rule="limit_runner_job_requests_by_runner_token"}` | Rate limiting of job requests |

### Logs

- Relay, Kibana index `pubsub-kas-inf-gprd-*`: [failed job requests](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.msg,json.mod_name,json.gl_project_path,json.commit_id,json.error_message,json.grpc_code,json.correlation_id,json.agent_key),filters:!(),index:'78f49290-709e-11eb-b821-df2c3b5b1510',query:(language:kuery,query:'json.msg:+"Failed+to+request+a+CI+job+from+GitLab"'))&_g=(time:(from:'now-6h',to:'now'))) (`Failed to request a CI job from GitLab`, with `json.grpc_code`) and [rate-limited job requests](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.msg,json.mod_name,json.gl_project_path,json.commit_id,json.error_message,json.grpc_code,json.correlation_id,json.agent_key),filters:!(),index:'78f49290-709e-11eb-b821-df2c3b5b1510',query:(language:kuery,query:'json.msg:+"GitLab+rate+limited+the+CI+job+request"'))&_g=(time:(from:'now-6h',to:'now'))). `json.correlation_id` follows one request; `json.agent_key` identifies the runner. `Unimplemented` and cancelled polls are not logged.
- Runner managers, `pubsub-runner-inf-gprd-*`: [router state changes](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.operation,json.job,json.operation,json.repo_url,json.project,json.msg,json.shard,json.runner,json.job_router_url,json.error_message),filters:!(),index:'pubsub-runner-inf-gprd',query:(language:kuery,query:'json.msg:+("Job+router+circuit+breaker+tripped,+falling+back+to+direct+job+requests"+OR+"Job+router+circuit+breaker+tripped+on+dial+failure,+falling+back+to+direct+job+requests"+OR+"Job+router+dial+failed,+falling+back+to+direct+job+requests"+OR+"Job+router+is+disabled,+falling+back+to+direct+job+requests"+OR+"Job+router+recovered,+resuming+routing"+OR+"Using+job+router+at")'))&_g=(time:(from:'now-6h',to:'now'))) (discovery, breaker trips, dial failures, disabled, recovered), [failed GetJob calls](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.operation,json.job,json.operation,json.repo_url,json.project,json.msg,json.shard,json.runner,json.correlation_id,json.error_message),filters:!(),index:'pubsub-runner-inf-gprd',query:(language:kuery,query:'json.msg:+"Error+requesting+a+job"'))&_g=(time:(from:'now-6h',to:'now'))), and [rate-limited polls](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.operation,json.job,json.operation,json.repo_url,json.project,json.msg,json.shard,json.runner,json.retry_after,json.correlation_id),filters:!(),index:'pubsub-runner-inf-gprd',query:(language:kuery,query:'json.msg:+"Checking+for+jobs...+rate+limited"'))&_g=(time:(from:'now-6h',to:'now'))). Filter on `json.shard`.
- Rails, `pubsub-rails-inf-gprd-*`: [the internal endpoint](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.status,json.method,json.meta.caller_id,json.meta.feature_category,json.path,json.request_urgency,json.duration_s,json.target_duration_s,json.correlation_id),filters:!((meta:(index:'7092c4e2-4eb5-46f2-8305-a7da2edad090',key:json.controller,negate:!t,params:GraphqlController,type:phrase),query:(match:(json.controller:(query:GraphqlController,type:phrase))))),index:'7092c4e2-4eb5-46f2-8305-a7da2edad090',query:(language:kuery,query:'json.route:+"/api/:version/internal/ci/job_router/jobs/request"'))&_g=(time:(from:'now-6h',to:'now'))), with the same `json.correlation_id`. See [Correlation IDs](#correlation-ids).
- Workhorse, `pubsub-workhorse-inf-gprd-*`: [the internal endpoint](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.method,json.remote_ip,json.status,json.uri,json.duration_ms,json.correlation_id),filters:!(),index:'a4f5b470-edde-11ea-81e5-155ba78758d4',query:(language:kuery,query:'json.uri:+"/api/v4/internal/ci/job_router/jobs/request"'))&_g=(time:(from:'now-6h',to:'now'))).

### Correlation IDs

- The runner creates the correlation ID. It is 32 lowercase hex characters. On the direct path the runner sends it as the `X-Request-Id` header. On the Job Router path it sends it as `x-request-id` gRPC metadata. Relay copies it into the header it sends to GitLab, and returns GitLab's ID to the runner.
- On the internal paths, through the internal gateway or through Relay, the ID reaches Rails unchanged. Workhorse keeps IDs that come from trusted internal addresses, and nginx and HAProxy pass the header through. The same `correlation_id` therefore appears in the runner, Relay, Workhorse, and Rails logs.
- Runners that reach gitlab.com through Cloudflare get a different ID. This applies to customer runners and to the shards that are not on [Private Service Connect](../ci-runners/ci-runner-networking.md#private-service-connect-for-runner-manager-traffic): the Windows and macOS managers. The Cells HTTP router Worker replaces the header with `<cf-ray>-<colo>`. The runner logs the ID it receives in the response, so runner and Rails logs still match. kas.gitlab.com is a Spectrum TCP application, so Cloudflare never rewrites Job Router requests.
- The shape of the ID shows where it was created. 32 hex characters means the runner created it. 16 hex characters followed by a colo code means Cloudflare did. [gitlab-runner#39944](https://gitlab.com/gitlab-org/gitlab-runner/-/work_items/39944) has the counts and the Kibana queries.

### Useful queries

```promql
# GetJob by gRPC code on Relay
sum by (grpc_code) (rate(grpc_server_handled_total{env="gprd", type="kas", grpc_service="gitlab.agent.job_router.rpc.JobRouter"}[5m]))

# GetJob by outcome, and the p95 for jobs actually returned
sum by (result) (rate(job_router_get_job_duration_seconds_count{env="gprd", type="kas"}[5m]))
histogram_quantile(0.95, sum by (le) (rate(job_router_get_job_duration_seconds_bucket{env="gprd", type="kas", result="job"}[5m])))

# Why runner requests bypassed the router, per shard
sum by (shard, reason) (rate(gitlab_runner_job_router_fallbacks_total{environment="gprd"}[5m]))

# Runner managers whose breaker is open or half-open, per shard
count by (shard) (gitlab_runner_job_router_circuit_breaker_state{environment="gprd"} > 0)

# The internal endpoint as Workhorse sees it
sum by (code) (rate(gitlab_workhorse_http_requests_total{env="gprd", route_id="api_job_router_jobs_request"}[5m]))

# Job requests blocked by the per-token rate limit
sum by (result) (rate(gitlab_labkit_rate_limiter_rule_evaluations_total{env="gprd", rule="limit_runner_job_requests_by_runner_token"}[5m]))
```

## Who to call

| For | Team | Where |
| ----- | ------ | ------- |
| The Job Router module, the SLI and alerts, the Rails flags | [Runner Core](https://handbook.gitlab.com/handbook/engineering/devops/runner/runner-core/) | `#g_runner_core` |
| Relay pods, Relay deploys, `kas.gitlab.com` | [Environments](https://handbook.gitlab.com/handbook/engineering/devops/runner/environments/), the Relay service owner | `#g_environments` |
| Runner shards and their configuration | [Runners Platform](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/runners-platform/) | `#g_runners_platform` |

## Reference

- SLI: `job_router` in [`metrics-catalog/services/kas.jsonnet`](../../metrics-catalog/services/kas.jsonnet)
- Dashboard source: [`dashboards/kas/job-router.dashboard.jsonnet`](../../dashboards/kas/job-router.dashboard.jsonnet)
- Runner client: [`router/`](https://gitlab.com/gitlab-org/gitlab-runner/-/tree/main/router) in gitlab-runner. Relay module: [`internal/module/job_router/`](https://gitlab.com/gitlab-org/cluster-integration/gitlab-agent/-/tree/master/internal/module/job_router) in gitlab-agent
- [Readiness assessment](https://gitlab.com/gitlab-org/architecture/readiness/-/tree/main/features/job_router)
- Runner documentation: [feature flags](https://docs.gitlab.com/runner/configuration/feature-flags/) and [rate limiting](https://docs.gitlab.com/runner/configuration/proxy/#handling-rate-limited-requests)
