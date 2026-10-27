# RunnerManagerNotRequestingJobs

A runner manager completed no job request in 10 minutes, for 10 minutes. A manager polls continuously whether or not there is work (about 15 long-polls per 10 minutes on either path, each returning a job or nothing), so zero means it stopped polling. The pod stays Ready and logs nothing while this lasts.

The rule counts job requests on both paths, `GetJob` through the Job Router and `POST /api/v4/jobs/request` directly, so it covers every Kubernetes shard whether or not `FF_USE_JOB_ROUTER` is on. A manager that fell back to direct polling after a router breaker trip is still polling and does not fire it. The Chef VM managers are outside the `runner-managers-*` clusters the rule selects and are not covered.

## Impact

The manager runs no new jobs until it polls again. On a shard with `request_concurrency = 1` one stuck request is enough.

## Causes seen so far

1. **Worker disabled by the health check.** Three job requests in a row judged unhealthy disable the worker for `unhealthy_interval` (1h by default). `gitlab_runner_worker_health_check_failures_total` for the pod increases and the log has `Runner ... is unhealthy and will be disabled`. The `Error requesting a job` lines before it have the response. Only a `PermissionDenied` (HTTP 403) counts as unhealthy on the job router path, as a 403 does on the direct path, so this points at the runner token. Managers older than Runner 19.4 counted every failed request, including a `FailedPrecondition` (409, another manager took the job), which disabled managers on busy shards. Restarting the pod clears it early. If a whole shard shows this and the cause is the request path rather than the token, turn `FF_USE_JOB_ROUTER` off for the shard and open a runner issue with the response.
2. **A request that never returns.** `gitlab_runner_request_concurrency` for the pod stays at its configured maximum, the health check counter does not move, nothing is logged. Observed on the private shard for 30 to 60 minutes at a time, several pods at once, ending on their own. Restarting the pod releases it.

## What to check

- How many pods on the shard fire at once. A handful is the known pattern; all of them points at the request path, Relay for a routing shard or the internal gateway for a direct one.
- The rule only considers managers with a free job slot (`gitlab_runner_jobs` below `concurrent` and `limit`); one at capacity stops requesting until a job finishes and does not fire.
- A rate-limited manager still polls, so it does not fire this alert. A 429 from GitLab arrives as `ResourceExhausted`. On Runner 19.5 and later it is logged as `Checking for jobs... rate limited` with `retry_after` and counted in `gitlab_runner_job_router_get_job_requests_total{code="ResourceExhausted"}`, or on the direct path in `gitlab_runner_api_request_attempts_total{endpoint="request_job", status="429"}`; older managers log `Error requesting a job` with `ResourceExhausted` in the error and count it under `result="error"` in `gitlab_runner_job_router_get_job_duration_seconds`. Slow job pickup with rate-limited requests rising is rate limiting (`runner_jobs_request_api_limit`), not a stuck manager.
