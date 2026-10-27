# GitalyOOMKillLoop

## Overview

Gitaly on one node is being OOM-killed and restarted repeatedly: the kernel has
killed at least one process on the node and the Gitaly process has started at
least twice, both within ten minutes. Each restart brings the process back into
the same demand, so without intervention the loop continues for hours.

Nothing else pages for this pattern. Each kill costs 60 to 150 seconds of
downtime, so `GitalyFileServerDown` (which needs five minutes of continuous
`up == 0`) never fires, and the service-level alerts need the error budget to
burn first. In the incident this alert comes from (INC-14259, 2026-09-17), the
loop ran for 12.5 hours; the first page was the `client_calls` SLI, 33 minutes
after the first kill, and it said "error rate", not "kill loop".

The usual cause is one repository whose shape makes some per-request work very
expensive in memory (an amplifier), under steady traffic from one client. The
specific amplifier behind INC-14259 has been removed (see the worked example),
so treat this page as a pattern: find what is being killed, find the
repository and the caller, and stop the amplifier.

## Services

- [Service Overview](../README.md)
- Team that owns the service: [Tenant Scale:Gitaly
  Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)

## Metrics

The alert joins two series on the node (`fqdn`); they carry different `job`
labels, hence the `on (fqdn)`:

```promql
(increase(node_vmstat_oom_kill{env="gprd", type="gitaly"}[10m]) >= 1)
and on (fqdn)
(changes(process_start_time_seconds{job="scrapeConfig/monitoring/prometheus-agent-gitaly", env="gprd", type="gitaly"}[10m]) >= 2)
```

- `node_vmstat_oom_kill` counts kernel OOM kills on the node, including kills
  inside a cgroup. It is in the "OOM Kills on Node" panel of the host detail
  dashboard.
- `process_start_time_seconds` for the Gitaly scrape job changes every time the
  Gitaly process starts; `changes(...[10m]) >= 2` means at least two restarts in
  ten minutes.
- `for: 10m`. In a replay of INC-14259 the expression first held at 19:47 UTC,
  six minutes after the first kill, and a ten-minute `for` fires at 19:57.

## Alert Behavior

- Kills alone are not a signal: `git` child processes are killed inside their
  cgroups routinely (up to 88 in ten minutes on one node in a 26-day sample)
  with no Gitaly restart. Restarts alone are deploys and single restarts (never
  more than two in ten minutes in the same sample). The two together on the
  same node did not occur once in 26 days outside the incident.
- During INC-14259 the node showed 2 to 3 kills and 2 to 3 Gitaly restarts per
  ten minutes, steadily, for 12.5 hours.
- `GitalyRequestsDropped` (s3, not paging) usually fires first, within minutes
  of the first kill; it is a symptom of the same node.

## Severities

- **s2**, paging, in `gprd`. A node in a kill loop is unavailable to every
  repository on it; the errors reach users immediately.
- **s4** in `gstg` and `pre`, where the thresholds are not sized.

## Verification

1. **Confirm the loop.** Host detail dashboard for the node: "OOM Kills on
   Node", memory RSS of the Gitaly process (a sawtooth climbing to the limit),
   and the restart count from the alert's linked query. One or two kills with
   no further restarts is not this alert.
2. **Do not restart the VM.** The cause is demand plus an amplifier; a restart
   brings the process back with empty caches into the same demand. In
   INC-14259 the VM restart at 02:06 cost 120 seconds of extra downtime and
   left the kill cadence unchanged at 2 to 3 per ten minutes.
3. **Find what was killed.** In Kibana, the system logs for the node (the
   saved search linked from the [Gitaly README](../README.md)): search both
   `Out of memory: Killed process` and `Memory cgroup out of memory: Killed
   process`. A `git` child killed in its cgroup is routine and does not match
   this alert; a `gitaly` process kill does. The unit's memory limit comes from
   `systemctl show gitlab-runsvdir -p MemoryLimit -p MemoryMax` on the node.
4. **Find the repository and the caller.** In Kibana on
   `pubsub-gitaly-inf-gprd*` with `json.fqdn.keyword` set to the node, from ten
   minutes before the first kill: group by `json.grpc.request.glProjectPath.keyword`
   and `json.grpc.method.keyword`; look at `json.grpc.time_ms`, the
   `ResourceExhausted` concentration and `json.limit.limiting_key`. One
   repository and one method dominating is the amplifier. For the heap, between
   two kills (the process lives two to three minutes):
   `curl -o heap.bin http://localhost:9236/debug/pprof/heap` on the node, then
   `go tool pprof -top heap.bin`; see
   [gitaly-profiling.md](../gitaly-profiling.md). One handler holding most of
   the live heap names the amplifier. The caller is `json.caller_id` on the
   same log lines: a Rails route, or a Sidekiq worker class.

## Troubleshooting and Resolution

1. **Stop the amplifier.** First decide from step 4 who is calling: a signed-in
   user or a scheduled job, or anonymous clients.
   - Signed-in user: block the user as an admin, as in "Block a User or
     Project" in [rate-limiting/README.md](../../rate-limiting/README.md#block-a-user-or-project).
     Blocking the owner does not stop imports already running; cancel them
     with [cancel-running-imports.md](../../importers/cancel-running-imports.md).
   - The repository itself: [block-high-load-project.md](../../uncategorized/block-high-load-project.md)
     sets the project to Private, turns the Repository feature off and blocks
     the owner.
   - Anonymous clients, or a source IP or path: Cloudflare, per
     [managing-traffic.md](../../cloudflare/managing-traffic.md#when-to-block-and-how-to-block).
     The "Block the repo" remedy in
     [git-high-cpu-and-memory-usage.md](../git-high-cpu-and-memory-usage.md#remedies)
     (Bouncer, or Private) blocks anonymous clients only and will not stop a
     signed-in caller.
   - A Sidekiq worker (`json.caller_id` is a worker class, for example a
     scheduled job): [defer the worker
     class](../../sidekiq/disabling-a-worker.md#incident-quick-reference).
     Check this even after the user is blocked: in INC-14259 the user was
     blocked at 22:41 and the loop continued for nine more hours because
     scheduled jobs kept calling the same RPC on the same repository.

   Then watch "OOM Kills on Node" on the host detail dashboard: the loop has
   stopped when the node goes ten minutes without a kill or a restart.
2. **If it does not settle,** move the repository off the node and page the
   Gitaly Tier 2 rotation with the node, the repository path and the heap
   profile.
3. **Afterwards,** the amplifier is a Gitaly bug: file it in `gitlab-org/gitaly`
   with the profile. The fix is in Gitaly, not in the node's memory limit.

`gitaly_cgroup_memory_events_max_total` is a background signal only: it counts
reclaim at the repository cgroups on every node (a median of about 2,000
increases per four hours fleet-wide) and does not indicate this loop.

## Worked example: INC-14259

2026-09-17 19:41 UTC to 2026-09-18 08:12 UTC, one `gprd` node. Measured in
Mimir after the fact: about 150 kernel kills and 138 Gitaly restarts between
19:50 and 08:20, a steady 2 to 3 of each per ten minutes; the longest
`up == 0` run was 150 seconds, so `GitalyFileServerDown` never fired on the
loop; `GitalyRequestsDropped` fired at 19:44 without paging; the first page
was the `client_calls` SLI at 20:14. The user was blocked at 22:41 with no
effect because scheduled jobs kept hitting the repository; the VM was
restarted at 02:06 with no effect on the cadence.

The amplifier: a large imported repository with a very large number of loose
entries, and housekeeping middleware that walked those entries synchronously
inside every read RPC. That code is gone from every deployed build:
[gitaly!9283](https://gitlab.com/gitlab-org/gitaly/-/merge_requests/9283)
claimed the stats-cache key before the walk, and
[gitaly!9297](https://gitlab.com/gitlab-org/gitaly/-/merge_requests/9297)
removed the accessor trigger altogether. This exact instance cannot recur; the
pattern can, with a different amplifier.

## Escalation

Gitaly has a Tier 2 rotation. Follow the [How to
Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)
guidance to page the team.

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)
- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)

## Definitions

- [Alert
  definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules-jsonnet/gitaly-oom-kill-loop.jsonnet)
- Related: INC-14259,
  [gitaly#7432](https://gitlab.com/gitlab-org/gitaly/-/issues/7432),
  [GitalyRequestsDropped](GitalyRequestsDropped.md),
  [GitalyFileServerDown](GitalyFileServerDown.md),
  [gitaly-repos-cgroup.md](../gitaly-repos-cgroup.md)
- [Update the template used to format this
  playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
