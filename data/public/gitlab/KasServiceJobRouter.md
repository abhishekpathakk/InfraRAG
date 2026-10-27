# KasServiceJobRouter alerts

This page covers the alerts generated from the `job_router` SLI of the GitLab Relay (`kas`) service:

| Alert | Severity | Pages? | Measures |
| --- | --- | --- | --- |
| [`KasServiceJobRouterErrorSLOViolation`](#kasservicejobroutererrorsloviolation) | `s2` | yes (PagerDuty) | Too many `GetJob` calls failing on Relay's side. The error ratio is burning the 99.5% SLO. |
| [`KasServiceJobRouterTrafficCessation`](#kasservicejobroutertrafficcessation-and-kasservicejobroutertrafficabsent) | `s2` | yes (PagerDuty) | The 30-minute `GetJob` rate at zero for 5 minutes, for an SLI that was running at 10 or more requests per minute an hour earlier. |
| [`KasServiceJobRouterTrafficAbsent`](#kasservicejobroutertrafficcessation-and-kasservicejobroutertrafficabsent) | `s2` | yes (PagerDuty) | The `GetJob` rate series missing for 30 minutes, after being present an hour earlier. |

Runners with the Job Router enabled request CI jobs from Relay over gRPC (`GetJob`) instead of polling Rails directly. Read the [Job Router page](../job-router.md) first if the feature is new to you.

The runner is built to survive the router. When Relay is unreachable, the runner's circuit breaker trips after three consecutive failures spanning 5 seconds and the runner polls Rails directly until Relay answers again. So a Job Router problem usually costs job pickup time on the routed shards, not jobs. The exception is when Rails or Workhorse is the cause, because then the direct path is failing too. For every alert here, the first question is the same: are runners falling back cleanly, and is the direct path healthy?

## Services

- [Job Router dashboard](https://dashboards.gitlab.net/d/kas-job-router)
- [Relay overview](https://dashboards.gitlab.net/d/kas-main), where the SLI is drawn against its SLO
- Owner: [Runner Core](https://handbook.gitlab.com/handbook/engineering/devops/runner/runner-core/) (`#g_runner_core`), the SLI's owner. Its alerts post to `#alerts-ci-cd` through `feature_category: runner_core`, and its error budget report goes to `#ci-section` through `team: runner_core`. The page goes to the SRE on-call. Relay itself: [Environments](https://handbook.gitlab.com/handbook/engineering/devops/runner/environments/) (`#g_environments`). The shards: [Runners Platform](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/runners-platform/) (`#g_runners_platform`).

## Alerts

### KasServiceJobRouterErrorSLOViolation

Too many `GetJob` calls are failing on Relay's side: Relay could not complete its call to GitLab.

What it does not mean: rejected runner tokens, rate limiting, another runner taking the job, or a deliberate rollback. Those come back as other gRPC codes and are not counted.

Impact: a runner whose `GetJob` fails returns no job for that poll and tries again after its check interval. If Relay keeps failing, the breaker trips and the runner polls Rails directly. So the usual cost is slower job pickup on the routed shards.

What to do: find out which of the causes below you have, confirm that runners are falling back and the direct path is healthy, and roll back to direct polling if the router path cannot be fixed quickly.

#### Metrics

The `job_router` SLI in [`kas.jsonnet`](../../../metrics-catalog/services/kas.jsonnet) counts `grpc_server_handled_total` for the `gitlab.agent.job_router.rpc.JobRouter` service. An error is any gRPC code except `OK`, `NotFound`, `PaymentRequired`, `FailedPrecondition`, `Unauthenticated`, `PermissionDenied`, `Canceled`, `DeadlineExceeded`, `ResourceExhausted`, and `Unimplemented`. In practice that is `Unavailable`, which Relay returns when its call to GitLab fails for any reason other than a 401, 403, 409, 422, 429, or 501. A poll the runner cancels comes back as `Canceled` and is not counted.

- SLO: 99.5% of calls without error, so an error budget of 0.5%.
- Alerting: the metrics catalog's standard multi-window, multi-burn-rate rule applied to this SLO, so the numbers follow from the 0.5% budget. The short pair (1 hour and 5 minutes) fires at a burn rate of 14.4, an error ratio above 7.2%, which spends 2% of a 30-day budget in an hour. The long pair (6 hours and 30 minutes) fires at a burn rate of 6, above 3%, which spends 5% of the budget in six hours. Both windows of a pair must breach, for 2 minutes, and the SLI must carry at least 1 request per second (0.17 for the long pair). See the [SLO alerting how-to](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/).
- Confidence interval: the ratio is evaluated at 98% confidence. Traffic follows how many runners are routed, and at low volume a handful of errors would otherwise page.
- Normal: the ratio sits near zero. Relay deploys produce short bursts of `Unavailable` as pods terminate; they do not last long enough to burn the budget.

#### Alert behavior

- Severity S2. It pages, and it posts to `#alerts-ci-cd` because the SLI carries `feature_category: runner_core`.
- Silence during a planned rollback or a planned Relay outage with the matchers `type="kas"` and `component="job_router"` on [alerts.gitlab.net](https://alerts.gitlab.net/#/silences/new).
- Expected to be rare.

#### Severities

Start at S2 and adjust:

- Stay at S2, or go to S1, when `POST /api/v4/jobs/request` on the direct path is also degraded. Then the cause is Rails or Workhorse and all CI is affected, not only the routed shards.
- Stay at S2 when errors persist for long without the breaker tripping. That happens when a fraction of calls fail on every poll: each failed poll costs the manager one check interval per request slot, and pickup on the routed shards slows for as long as it lasts.
- Lower to S3 when the runner-side panels show the breaker open across the routed shards and the direct path is healthy. Runners are on the direct path, pickup was delayed by seconds when the breaker tripped, and the Job Router is simply out of the picture until Relay recovers.

Who is affected: only projects whose jobs run on routed shards. The [Job Router page](../job-router.md#where-each-piece-runs-on-gitlabcom) says how to list them.

#### Verification

```promql
# What the alert evaluates: the error ratio at 98% confidence, long and short window
gitlab_component_errors:confidence:ratio_1h{component="job_router", confidence="98%", type="kas", env="gprd", monitor="global"}
gitlab_component_errors:confidence:ratio_5m{component="job_router", confidence="98%", type="kas", env="gprd", monitor="global"}

# Which codes are failing
sum by (grpc_code) (rate(grpc_server_handled_total{env="gprd", type="kas", grpc_service="gitlab.agent.job_router.rpc.JobRouter"}[5m]))

# Are runners falling back, and why
sum by (shard, reason) (rate(gitlab_runner_job_router_fallbacks_total{environment="gprd"}[5m]))
```

- The [Relay overview](https://dashboards.gitlab.net/d/kas-main) draws the SLI, its SLO, and the burn rate on the `job_router` rows.
- On the [Job Router dashboard](https://dashboards.gitlab.net/d/kas-job-router), `GetJob by Response Code` shows what is failing and `GetJob Requests/sec` whether traffic is still arriving.
- Relay logs: [`Unavailable` responses](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.msg,json.mod_name,json.gl_project_path,json.commit_id,json.error_message,json.grpc_code,json.correlation_id,json.agent_key),filters:!(),index:'78f49290-709e-11eb-b821-df2c3b5b1510',query:(language:kuery,query:'json.grpc_code:+"Unavailable"'))&_g=(time:(from:'now-6h',to:'now'))) and [failed job requests](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.msg,json.mod_name,json.gl_project_path,json.commit_id,json.error_message,json.grpc_code,json.correlation_id,json.agent_key),filters:!(),index:'78f49290-709e-11eb-b821-df2c3b5b1510',query:(language:kuery,query:'json.msg:+"Failed+to+request+a+CI+job+from+GitLab"'))&_g=(time:(from:'now-6h',to:'now'))), which carry the error and `json.correlation_id`. A poll the runner cancels comes back as `Canceled`, is not counted, and is not logged.

#### Troubleshooting

1. **Is it Relay or GitLab?** Open `GetJob by Response Code`. Then check the direct path on the [CI Runners incident dashboard](https://dashboards.gitlab.net/d/ci-runners-incident-gitlab-application) and the [API dashboard](https://dashboards.gitlab.net/d/api-main). If `POST /api/v4/jobs/request` is failing too, this is a Rails or Workhorse incident and the Job Router is a symptom. Treat it as such.
2. **What does Relay say?** Open [failed job requests](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.msg,json.mod_name,json.gl_project_path,json.commit_id,json.error_message,json.grpc_code,json.correlation_id,json.agent_key),filters:!(),index:'78f49290-709e-11eb-b821-df2c3b5b1510',query:(language:kuery,query:'json.msg:+"Failed+to+request+a+CI+job+from+GitLab"'))&_g=(time:(from:'now-6h',to:'now'))) in Kibana. The error text says whether Relay could not connect, timed out, or got a 5xx from Workhorse. Take a `json.correlation_id` to the [Rails](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.status,json.method,json.meta.caller_id,json.meta.feature_category,json.path,json.request_urgency,json.duration_s,json.target_duration_s,json.correlation_id),filters:!((meta:(index:'7092c4e2-4eb5-46f2-8305-a7da2edad090',key:json.controller,negate:!t,params:GraphqlController,type:phrase),query:(match:(json.controller:(query:GraphqlController,type:phrase))))),index:'7092c4e2-4eb5-46f2-8305-a7da2edad090',query:(language:kuery,query:'json.route:+"/api/:version/internal/ci/job_router/jobs/request"'))&_g=(time:(from:'now-6h',to:'now'))) and [Workhorse](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.method,json.remote_ip,json.status,json.uri,json.duration_ms,json.correlation_id),filters:!(),index:'a4f5b470-edde-11ea-81e5-155ba78758d4',query:(language:kuery,query:'json.uri:+"/api/v4/internal/ci/job_router/jobs/request"'))&_g=(time:(from:'now-6h',to:'now'))) logs for the internal endpoint to see how far the request got.
3. **Is the internal endpoint healthy?** `gitlab_workhorse_http_requests_total{route_id="api_job_router_jobs_request"}` by `code`. 5xx here is Rails; no traffic here while Relay reports `Unavailable` means Relay cannot reach Workhorse.
4. **Is Relay itself in trouble?** Saturation and pod restarts on the [Relay overview](https://dashboards.gitlab.net/d/kas-main), `kubectl -n gitlab get pods -l app=kas`, and the [Relay Sentry project](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=11). A deploy in progress explains a short burst. A pod crash-looping or out of memory explains a sustained one.
5. **Are runners falling back?** On the runner-side row, `Runner-side Fallbacks/sec` and `Runner-side Circuit Breakers Not Closed`. Breakers open across the shards means runners are on the direct path and the user impact is bounded. Breakers closed while errors continue means a fraction of calls are failing and pickup is slow. Note that `Runner-side Circuit Breakers Not Closed` is empty both when every breaker is closed and when nothing reports; `Runner-side GetJob Outcomes/sec` tells you which.
6. **Are the errors real?** A poll the runner cancels, for example on shutdown, comes back as `Canceled`, which is not counted, so a shard restart or deploy does not show up here. What counts is Relay failing to complete its call to GitLab.
7. **Mitigate.** If the cause is on the router path and not fixed within a few minutes, turn the Rails flag off, globally if it is enabled globally, since a per-group disable then has no effect. Runners are on the direct path within one poll. Details and verification in the [Job Router page](../job-router.md#rollback).

#### Possible resolutions

- Relay could not reach Workhorse or GitLab: fix the network path or the Rails incident. The Job Router recovers on its own; runners resume routing when their trial request succeeds and log `Job router recovered, resuming routing`.
- A Relay regression: roll Relay back. Turn the Rails flag off meanwhile if runners are not falling back cleanly.
- A shard restart or rolling deploy of runner managers: nothing to do, the burst ends with the restart.
- Rails 5xx on the internal endpoint: a Rails incident. The direct endpoint shares the code path for acquiring a job, so expect it to be failing too.

No incidents so far have been caught by this alert; add them here as they happen.

### KasServiceJobRouterTrafficCessation and KasServiceJobRouterTrafficAbsent

Runners with the Job Router enabled call `GetJob` on every poll, whether or not there is work, so the rate never drops to zero while any routed runner can reach Relay. Zero means every routed runner has stopped calling. Either they were told to stop, through one of the two feature flags, or they cannot get through.

Impact depends on the cause. If a flag was turned off, runners are polling Rails directly and CI is unaffected; this is the expected result of a rollback. If runners cannot reach Relay, their circuit breakers have tripped and they are polling Rails directly too; CI continues, and the Job Router is out of the path until Relay is reachable again. In both cases, confirm that the direct path is carrying the load.

#### Metrics

Both alerts use the request rate of the `job_router` SLI. Cessation uses the 30-minute rate and fires once it has been zero for 5 minutes while the same rate an hour earlier was 10 or more requests per minute, so it only fires for an SLI that was in use. Absent uses the 5-minute rate and fires when the series has been missing for 30 minutes while it existed an hour earlier. The series disappears when every pod that had served a `GetJob` has been replaced and no new pod has served one, or when Relay is not being scraped. Normal traffic is a steady rate that follows how many runner managers are routed and their poll intervals, with about 15 long polls per idle manager every 10 minutes.

#### Alert behavior

- Severity S2. Both page and post to `#alerts-ci-cd`.
- A rollback of the Rails flag or of a shard's runner flag makes this fire by design. Silence it before a planned rollback with the matchers `type="kas"` and `component="job_router"` on [alerts.gitlab.net](https://alerts.gitlab.net/#/silences/new), and note the silence in the change or incident.
- Otherwise rare.

#### Severities

- Planned rollback, flag off on purpose: no incident. Resolve the alert.
- Runners cannot reach Relay, direct path healthy: S3. CI continues on the direct path. Fix Relay or the network path at normal pace.
- Runners cannot reach Relay and the direct path is degraded: S2 or higher. This is an API or Workhorse incident and the Job Router is a symptom.

Who is affected: only projects whose jobs run on routed shards, as above.

#### Verification

```promql
# What the alert evaluates
gitlab_component_ops:rate_30m{component="job_router", type="kas", env="gprd", monitor="global", stage="main"}

# Raw GetJob rate per Relay pod
sum by (pod) (rate(grpc_server_handled_total{env="gprd", type="kas", grpc_service="gitlab.agent.job_router.rpc.JobRouter"}[5m]))

# What the runners are doing instead: fallbacks by reason, and polls by outcome
sum by (shard, reason) (rate(gitlab_runner_job_router_fallbacks_total{environment="gprd"}[5m]))
sum by (shard, result) (rate(gitlab_runner_job_router_get_job_duration_seconds_count{environment="gprd"}[5m]))
```

- `GetJob Requests/sec` on the [Job Router dashboard](https://dashboards.gitlab.net/d/kas-job-router) is flat at zero.
- The runner-side row still shows activity. `Runner-side Fallbacks/sec` names the reason runners are bypassing the router, and that reason is the diagnosis. The [runner log lines](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.operation,json.job,json.operation,json.repo_url,json.project,json.msg,json.shard,json.runner,json.job_router_url,json.error_message),filters:!(),index:'pubsub-runner-inf-gprd',query:(language:kuery,query:'json.msg:+("Job+router+circuit+breaker+tripped,+falling+back+to+direct+job+requests"+OR+"Job+router+circuit+breaker+tripped+on+dial+failure,+falling+back+to+direct+job+requests"+OR+"Job+router+dial+failed,+falling+back+to+direct+job+requests"+OR+"Job+router+is+disabled,+falling+back+to+direct+job+requests"+OR+"Job+router+recovered,+resuming+routing"+OR+"Using+job+router+at")'))&_g=(time:(from:'now-6h',to:'now'))) behind it say the same in words.
- Flag state: `/chatops run feature get job_router` and `/chatops run feature get job_router_instance_runners`. Recent changes are in [feature-flag-log](https://gitlab.com/gitlab-com/gl-infra/feature-flag-log/-/issues/?search=job_router).

#### Troubleshooting

Read the `reason` on `Runner-side Fallbacks/sec`:

1. **`router_disabled`**, and `Unimplemented` on `GetJob by Response Code` just before the traffic stopped: the Rails flag is off. Check whether it was intentional in feature-flag-log. If it was, resolve the alert. If not, find out who turned it off before turning it back on.
2. **`no_discovery`**: discovery did not return a router. 501 is the flag off, or Relay disabled in the Rails configuration, seen by runners that had no cached router. It is also recorded for a 403, a 5xx, or a failed request, and any of these is cached for five minutes, so one bad answer keeps that manager on the direct path for that long. The runner log line `Discovering Job Router...` has the status.
3. **`dial_failed`**: runners cannot open a connection to `kas.gitlab.com`. The runner log line `Job router dial failed` ([Kibana](https://log.gprd.gitlab.net/app/kibana#/discover?_a=(columns:!(json.operation,json.job,json.operation,json.repo_url,json.project,json.msg,json.shard,json.runner,json.job_router_url,json.error_message),filters:!(),index:'pubsub-runner-inf-gprd',query:(language:kuery,query:'json.msg:+("Job+router+circuit+breaker+tripped,+falling+back+to+direct+job+requests"+OR+"Job+router+circuit+breaker+tripped+on+dial+failure,+falling+back+to+direct+job+requests"+OR+"Job+router+dial+failed,+falling+back+to+direct+job+requests"+OR+"Job+router+is+disabled,+falling+back+to+direct+job+requests"+OR+"Job+router+recovered,+resuming+routing"+OR+"Using+job+router+at")'))&_g=(time:(from:'now-6h',to:'now')))) has the error: DNS, TLS handshake, connection refused, or a timeout. Check the HAProxy gRPC backend for Relay on the [Relay overview](https://dashboards.gitlab.net/d/kas-main) transport row and the [frontend runbook](../../frontend/README.md), and the certificate on `kas.gitlab.com`.
4. **`breaker_tripped` followed by a steady `breaker_open`**: connections open but `GetJob` fails with `Unavailable`, `DeadlineExceeded`, or `Canceled`. Relay is up at the transport level but not answering. Check Relay pods, saturation, and Sentry as in the [error alert's troubleshooting](#troubleshooting). Runners retry Relay with one trial request every 30 seconds and resume on their own when it answers.
5. **No fallbacks either, and the runner-side row is flat**: the shards stopped polling altogether, or the shard flag was removed. Check `gitlab_runner_jobs` and `gitlab_runner_request_concurrency` for the shards, `RunnerManagerNotRequestingJobs`, and the shard configuration. If the runner-side metrics are absent, the runner managers or their scraping are the problem, not Relay.
6. **Traffic absent with everything else healthy**: Relay's metrics stopped being scraped. Check the Relay pods' `/metrics` and the Prometheus targets for `type="kas"` before anything else.

#### Possible resolutions

- Rollback done on purpose: resolve, and re-enable when ready. Runners rediscover the router within five minutes or on restart.
- Flag turned off by mistake: turn it back on. Traffic returns within five minutes as discovery caches expire, faster if the shards are restarted.
- Relay unreachable: restore Relay or the HAProxy backend. No runner action is needed; breakers close on the first successful trial request.

## Recent changes

- [Production change requests in progress](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name[]=change%3A%3Ain-progress)
- Relay ships with the GitLab auto-deploy through [k8s-workloads/gitlab-com](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=merged). A deploy in progress explains a short burst of `Unavailable`; it does not stop traffic, because runners are designed to ride out a rolling deploy without tripping their breakers.
- Runner shard configuration: [argocd-apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged&search=runner) and [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests?scope=all&state=merged&search=runners-manager). A change that removes `FF_USE_JOB_ROUTER` from a shard stops that shard's traffic.
- Feature flags: [feature-flag-log](https://gitlab.com/gitlab-com/gl-infra/feature-flag-log/-/issues/?search=job_router).
- `kas.gitlab.com` on HAProxy: [gitlab-haproxy](https://gitlab.com/gitlab-cookbooks/gitlab-haproxy/-/merge_requests?scope=all&state=merged&search=kas). The gRPC backend is health-checked on Relay's `/readiness`; a change there can take the whole backend down while Relay is fine.
- Rollback is in the [Job Router page](../job-router.md#rollback). The Rails flag is the fast path and needs no deploy.

## Dependencies

- Rails and Workhorse: every `GetJob` becomes an HTTP request to the internal endpoint. Workhorse also holds the long poll.
- HAProxy: `kas.gitlab.com` fronts Relay. A gRPC backend problem shows up on the runner side as dial failures, and on this page as traffic stopping rather than as errors, because the calls never reach Relay.
- Relay pods and their metrics scraping.
- The `job_router` Rails flags, evaluated on every discovery and job request.

## Escalation

Escalate when:

- The cause is not clear after the troubleshooting steps and the alert has been firing for more than 30 minutes.
- Runners are not falling back: errors continue and the breakers stay closed, so pickup on the routed shards is degraded.
- The flags are on and runners still cannot reach Relay.
- The direct path is failing too. This is then a GitLab API or Workhorse incident and follows the normal incident process.
- Relay is unhealthy for reasons unrelated to the Job Router, such as crash loops or saturation.
- The flag was turned off by someone else and nobody can say why.

Where:

- Runner Core owns the module, the SLI, and the flags: `#g_runner_core`.
- Environments owns the Relay service: `#g_environments`.
- Runners Platform owns the shards and their configuration: `#g_runners_platform`.
- `#production` for anything at S2 or above.

## Definitions

- Alert source: the `job_router` SLI in [`metrics-catalog/services/kas.jsonnet`](../../../metrics-catalog/services/kas.jsonnet). The SLO (99.5%) and confidence interval (98%) are set there; the traffic alerts use the metrics catalog defaults. The [generated alert rules for gprd](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/kas/autogenerated-gitlab-gprd-kas-service-level-alerts.yml) are what actually fires.
- Tuning: do not add an apdex to this SLI without a threshold from the `result="job"` histogram; `grpc_server_handling_seconds` is dominated by the long poll and any threshold on it is meaningless. Do not count `Unimplemented`; it is the rollback signal.
- One page for three alerts because the SLI's `alertRunbook` is a single link that every alert generated from the SLI carries.
- [Edit this page](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kas/alerts/KasServiceJobRouter.md)

## Related Links

- [All Relay alerts](./) and the [Relay alerts table](../README.md#alerts)
- [Job Router page](../job-router.md)
- [`RunnerManagerNotRequestingJobs`](../../ci-runners/alerts/RunnerManagerNotRequestingJobs.md), the runner-side alert
- [SLO alerting how-to](https://gitlab-com.gitlab.io/gl-infra/observability/docs-hub/alert-routing/howto-slo-alerting/)
