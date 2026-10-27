# Project authorization refresh fan-out

Owned by the [Authorization Group](https://handbook.gitlab.com/handbook/engineering/development/sec/security-platform/authorization/).

Covers `AuthorizedProjectsWorker` and the `AuthorizedProjectUpdate::*` workers.

## 1. Triage

### 1.1 Confirm authorization refresh is the source

Open the [Sidekiq worker detail dashboard for all four workers](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=AuthorizedProjectsWorker&var-worker=AuthorizedProjectUpdate::ProjectRecalculateWorker&var-worker=AuthorizedProjectUpdate::UserRefreshFromReplicaWorker&var-worker=AuthorizedProjectUpdate::UserRefreshWithLowUrgencyWorker&from=now-6h&to=now)
and check the enqueue rate. Check if the enqueue rate for at least one of these workers is well above its
trailing 24h baseline.

### 1.2 Confirm safety net is the root cause

The safety net path tags every job it enqueues with
`meta.authorized_projects_refresh_purpose: safety_net`, so you can separate the two paths directly
in the logs. Run this in Kibana (data view `pubsub-sidekiq-inf-gprd-*`):

```text
json.meta.authorized_projects_refresh_purpose : "safety_net"
```

[Open this query in Kibana](https://log.gprd.gitlab.net/app/discover#/?_g=%28time%3A%28from%3Anow-6h%2Cto%3Anow%29%29&_a=%28columns%3A%21%28%27json.class%27%2C%27json.meta.caller_id%27%2C%27json.meta.root_caller_id%27%2C%27json.meta.root_namespace%27%2C%27json.meta.user%27%29%2Cindex%3A%27AWNABDRwNDuQHTm2tH6l%27%2Cinterval%3Aauto%2Cquery%3A%28language%3Akuery%2Cquery%3A%27json.meta.authorized_projects_refresh_purpose%20%3A%20%22safety_net%22%27%29%2Csort%3A%21%28%21%28%27%40timestamp%27%2Cdesc%29%29%29)

Select `json.meta.root_namespace` field on the left sidebar to group the results by namespace. A fan-out is almost always concentrated in a single `root_namespace` with one dominant `root_caller_id`.


## 2. Incident response & escalation

### 2.1 Mitigate the fan out

Enable the
[`do_not_run_safety_net_auth_refresh_jobs`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/config/feature_flags/development/do_not_run_safety_net_auth_refresh_jobs.yml)
feature flag. This gates the `LOW_PRIORITY` branch of
[`UserProjectAccessChangedService`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/services/user_project_access_changed_service.rb),
so no new safety-net jobs are scheduled.

The primary workers keeps running by design, only the safety net workers are disabled. The flag only affects the enqueue site, so jobs already in the Sidekiq scheduled set still fire and run to completion. Expect the fan-out to taper over the next hour.

### 2.2 Rollback

Once the incident has been resolved, disable the feature flag. The safety net jobs repair `project_authorizations` rows that drifted from the source of truth. While the flag is enabled that repair is not running, so any drift the primary path misses goes uncorrected and affected users can keep seeing stale access.

Treat this as a temporary incident mitigation, not a steady state.

Record in the incident issue when the flag was enabled and disabled, and notify `#g_authorization` if it needs to stay on beyond the incident so the group can assess the correctness risk.

## 3. Background

### 3.1 Why it fans out

Project authorizations are cache for a user's access levels in projects. Any change to the user's access level / membership triggers a re-computation of this cache.

Every request schedules two workers - a primary worker (`AuthorizedProjectsWorker` or `ProjectRecalculateWorker` or `ProjectRecalculatePerUserWorker`) which is enqueued instantly. And a safety worker which is enqueued an hour later.

The safety nets read from the replica, however they usually cause the fan out becuase they trigger an access level recomputation for ever member in the group in which the membership change occured.

All the different workers write to the same `project_authorizations` table which results in a high number of writes and WAL accumulation on the table.

### 3.2 Common triggers

Not exhaustive, but these are what we have seen cause bursts:

- SAML/SCIM group sync — calls the per-member callback once per member, so a sync of a large group
  enqueues one job per member.
- Group sharing and unsharing, and project/group link create, update, or destroy.
- Bulk member add, remove, activation, or await (seat management).
- Project creation under a group, project transfer, and namespace transfer or path change.

## Related

- [`do_not_run_safety_net_auth_refresh_jobs` rollout issue](https://gitlab.com/gitlab-org/gitlab/-/issues/390336)
- [`Project Authorizations Performance Enhancements`](https://gitlab.com/groups/gitlab-org/-/work_items/22633) —
  ongoing application-side work on the underlying cost of a refresh
- [`Heavy recursive queries on group membership updates`](https://gitlab.com/groups/gitlab-org/-/work_items/8200)
- [`sidekiq_queueing` apdex violation](../../sidekiq/sidekiq-queueing-apdex.md)
- [Sidekiq sharding](../../sidekiq/sharding.md)
