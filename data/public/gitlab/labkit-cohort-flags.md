# LabKit cohort flags: levers by symptom

This page applies to GitLab.com and GitLab Dedicated.
It covers the six cohort flags that control the LabKit rack rate limiter while it runs next to Rack::Attack.
On GitLab.com, it also covers the tier-aware flags, because they start the same middleware.
The cohort flags are removed in GitLab 19.7 ([production-engineering#29663](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29663)).

## How the flags work

The LabKit middleware runs directly above Rack::Attack.
Each Rack::Attack throttle has a LabKit rule, and each rule belongs to one of three cohorts.
Each cohort has two flags:

* `rate_limiter_use_labkit_rack_cohort_<n>`: the shadow flag.
* `rate_limiter_use_labkit_rack_cohort_<n>_enforce`: the enforce flag.

The flags do not act per cohort in the way their names suggest.
Three separate questions decide what happens to a request:

| Question | Answer |
| --- | --- |
| Does the middleware run? | Yes, when any cohort's shadow flag is on. On GitLab.com, also when any [tier-aware flag](#tier-aware-flags-gitlabcom-only) is on. |
| Which rules does it evaluate? | When it runs, it evaluates the rules of every cohort, whatever that cohort's flags are. |
| Does a block return a 429? | Yes, for a rule whose cohort has its `_enforce` flag on, even if that cohort's shadow flag is off. Yes, always, for a tier-aware rule, which has no cohort. Otherwise the request continues to Rack::Attack. |

So the `_enforce` flag, not the shadow flag, stops the LabKit 429s of a cohort.
If you turn off only the shadow flag of a cohort, its rules still return 429s whenever another flag starts the middleware.

| Cohort flags | Result for that cohort's rules |
| --- | --- |
| `_enforce` off | LabKit does not return a 429. Rack::Attack decides. |
| `_enforce` on | LabKit returns the 429 whenever the middleware runs, also when this cohort's shadow flag is off. |

The cohorts hold these throttles.
See [Rate limits in the Admin area](admin-area-limits.md) for the setting that controls each one.

| Cohort | Throttles |
| --- | --- |
| 1 | packages API, files API, deprecated API, dependency proxy, MCP server, incident management notifications, product analytics collector |
| 2 | web and API, authenticated and unauthenticated |
| 3 | Git HTTP, Git LFS, protected paths |

A `block` in the metrics is the limiter's decision, not a 429.
`gitlab_labkit_rate_limiter_checks_total{action="block"}` and `gitlab_labkit_rate_limiter_rule_evaluations_total{result="block"}` count a block in a cohort that does not enforce.
The middleware then lets the request continue to Rack::Attack.

### Tier-aware flags (GitLab.com only)

`Gitlab::RateLimit::FlagPolicy` lists 14 `gitlab_com_derisk` flags:

* `rate_limiter_plan_limits_<free|premium|ultimate>_info` and `_enforce`
* `rate_limiter_mcp_limits_<free|premium|ultimate>_info` and `_enforce`
* `rate_limiter_unauthenticated_limits_info` and `_enforce`

On GitLab.com, any one of them starts the middleware, whatever the cohort flags are.
Tier-aware rules have no cohort, so a tier-aware block always returns a 429.
To stop a tier-aware rule, see [Rolling back](README.md#rolling-back).

On GitLab Dedicated, these flags have no effect, and no tier-aware rules exist.
So on Dedicated, the six cohort flags alone decide whether the middleware runs.

### When every cohort enforces

When all six flags are on, LabKit owns rate limiting.
Rack::Attack then safelists every request (the `labkit_fully_enforced` safelist), so it throttles nothing.
A safelisted request writes no `gitlab_rack_attack_*` metric and no `Rack_Attack` log line.
So empty Rack::Attack panels are expected in this state.

When any one flag is off, Rack::Attack evaluates every throttle again, not only the throttles in that cohort.
For a cohort that still enforces, both limiters then apply: LabKit first, then Rack::Attack for the requests that LabKit allows.

## Find the source of a 429

1. Open the rate-limiting detail dashboard:
   * GitLab.com: [Rate limiting detail](https://dashboards.gitlab.net/d/rate-limiting-detail/rate-limiting-detail).
   * GitLab Dedicated: the `Rate limiting detail` dashboard in the tenant Grafana.
1. Look at the Workhorse 429 panels.
   They count the 429s that clients receive from every application-level limiter.
   On GitLab Dedicated, the panel splits them by `route_id`.
   Git routes (`git_*`) should almost never get a 429.
1. Find the limiter that returned the 429.
   Both limiters write to `auth.log`, which ships to the Rails log index.
   The `rate_limiter_rule_evaluations` SLI in the `rate-limiting` service overview links to both queries.

   | Limiter | `message` | Fields |
   | --- | --- | --- |
   | LabKit | `Rate_Limit_Block` | `matched` (throttle name), `rule`, `limit`, `period_s`, `count`, `counted_by` (the client that was counted), `applies_to` (what the rule matches) |
   | Rack::Attack | `Rack_Attack`, with `env` set to `throttle` | `matched` (throttle name), `remote_ip`, `user_id`, `path` |

   LabKit writes `Rate_Limit_Block` only for a block that it enforces.
   It writes the line when a client first goes over a rule's limit, and again at 2, 4 and 8 times the limit.
   So the number of lines is not the number of 429s.
   The line is in releases that contain [gitlab!258338](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/258338).
   It is not backported.
   On a release without it, a LabKit 429 has no log line, and only the metrics show it.
1. To confirm with one client, look at the `RateLimit-Name` header of the 429 response.
   It names the throttle.
   LabKit sends the same header as Rack::Attack, so the header does not tell you which limiter returned the 429.

## Levers by symptom

| Symptom | Lever | Effect |
| --- | --- | --- |
| Wrong 429s: LabKit counts requests under the wrong throttle | Turn off the `_enforce` flag of the affected cohort, or all three `_enforce` flags. Do not use the shadow flag for this. | LabKit stops blocking for those cohorts but can continue to classify. Rack::Attack enforces. |
| Audit-event flood and Redis pressure from LabKit classification | Turn off all six cohort flags. On GitLab.com, also turn off every tier-aware flag that is on. | LabKit stops running. The Rack::Attack share of the events continues. |

Change the flags the usual way for the platform:

* GitLab.com: use ChatOps, for example `/chatops run feature set rate_limiter_use_labkit_rack_cohort_2_enforce false`.
* GitLab Dedicated: follow the GitLab Dedicated process to change a feature flag on a tenant.

### Wrong 429s

An example is a LabKit rule that counts CI job token Git and LFS requests per IP under `throttle_unauthenticated_web`.
That bug was fixed in [gitlab!257711](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/257711), with backports to 19.4 and 19.3.

1. Find the throttle in the `matched` field of the `Rate_Limit_Block` line, or in the `RateLimit-Name` header.
1. Find the cohort of that throttle in the cohort table above.
   On GitLab.com, a name that contains `_traffic_per_` is a tier-aware rule and has no cohort.
   For those, see [Rolling back](README.md#rolling-back) instead.
1. Turn off the `_enforce` flag of that cohort.
   Do not turn off only the shadow flag: the cohort's rules still return 429s while any other flag starts the middleware.
   If you cannot find the cohort, turn off all three `_enforce` flags.
   If every cohort enforced before the change, Rack::Attack now evaluates all throttles again.
   Its panels and `Rack_Attack` log lines start to show data.
1. Check the Workhorse 429 panels.
   The 429 rate goes down within a few minutes.
   The LabKit panels continue to show `block`, because LabKit still classifies in shadow mode.
   This is expected.
1. If the 429s continue, Rack::Attack returns them.
   Find the throttle in the `Rack_Attack` log lines.
   Then check its limit in the Admin area.

### Audit-event flood and Redis pressure

Symptom: ElastiCache Redis memory grows on a Dedicated tenant, and `queue:audit_events` is the largest key.
To get from any large Sidekiq queue key to the code that fills it, see "Find the producer of a large Sidekiq queue" in the Dedicated ElastiCache runbook (`runbooks/elasticache-redis-alerts.md` in the GitLab Dedicated team project).

In shadow mode, LabKit resolves the identity of each request.
On affected releases, this writes an audit event for each `JOB-TOKEN` request ([gitlab#631338](https://gitlab.com/gitlab-org/gitlab/-/work_items/631338)).
Turning off the `_enforce` flags does not stop this, because shadow mode still classifies.

1. Turn off all six cohort flags.
1. On GitLab.com, also turn off every [tier-aware flag](#tier-aware-flags-gitlabcom-only) that is on.
   The middleware runs while any one of them is on.
   This also turns off the tier-aware limits, so agree on it with the incident lead first.
   On Dedicated, skip this step.
1. Check that the `rack_request`, `rack_request_protected_paths` and `rack_request_incident_management` limiters go quiet on the LabKit checks panel.
   Other limiters on that panel, for example the `applimiter_*` ones, come from application code and do not stop.
1. On GitLab.com, `RateLimitingServiceRateLimiterChecksTrafficCessation` can fire when the check rate drops.
   This is expected.
   Silence it for the duration of the change.
   The Dedicated service has no traffic-cessation alert, because this lever would set it off.

Turning off the flags is only a partial mitigation:

* Rack::Attack also calls the authentication chain.
  Its share of the audit events continues.
  On a busy instance, the audit event queue can continue to grow.
* The complete workaround is on the audit event streaming destination.
  Add an event type filter for `user_authenticated_using_job_token`, or turn off the streaming destination.
* [gitlab!259720](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/259720) removes the extra audit events.
  It is in GitLab 19.5 and later, and it is not backported to 19.4 or 19.3.
  Do not turn the flags back on for that instance until it runs 19.5 or later.
  If you turn them on before, the flood starts again.

## Open follow-ups

* No alert reads the 429 ratio or the block ratio.
  A limiter blocks on purpose, so a rising ratio can be expected, for example during an attack.
  The next step is an SLO for each ratio, set from the SLO analysis dashboard with data from GitLab.com and Dedicated.
  The SLIs stay `s3`, so they do not page.
  Anomaly detection fits these signals better, when [observability#4457](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/work_items/4457) is done.
