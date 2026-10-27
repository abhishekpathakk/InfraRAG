# Evaluate a hot repository for Packhorse caching

If a repository gets fetched a lot and puts heavy load on Gitaly, Packhorse
caching might help. To find out, you put the repository in Packhorse dry-run
mode, measure how much of its traffic the cache would serve, and then either
promote it to the caching allowlist or remove it.

Dry-run doesn't need any client-side change and doesn't disrupt traffic. Every
request still goes to Gitaly, and nothing is written to the cache.

## Where the config lives

You need to change two repositories. Without the chef change, no traffic reaches
Packhorse. Without the ArgoCD change, Packhorse gets the traffic but passes it
straight through to Gitaly.

- [`gitlab-com/gl-infra/chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo)
  decides which repos HAProxy sends to Packhorse, in
  [`roles/gprd-base-haproxy-ci.json`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-haproxy-ci.json).
- [`gitlab-com/gl-infra/argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps)
  decides whether Packhorse caches a repo, observes it in dry-run or passes it
  through, in
  [`services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml).

This runbook covers CI traffic. Non-CI traffic has its own `packhorse_repos` list
in
[`roles/gprd-base-haproxy-main.json`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-haproxy-main.json).

## 1. Route the repo to Packhorse

Open an MR to [`gitlab-com/gl-infra/chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo)
that adds the repo to `packhorse_repos` in
[`roles/gprd-base-haproxy-ci.json`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-haproxy-ci.json).
Paths start with `/` and end in `.git`.

```json
"packhorse_repos": [
  "/gitlab-org/gitaly.git",
  "/gitlab-org/gitlab.git",
  "/group/your-repo.git"
]
```

It takes about 30 minutes for chef-client to roll it out.

## 2. Enable dry-run

Open an MR to [`gitlab-com/gl-infra/argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps)
that adds the repo to `packhorse.dryRun.repositories` in
[`values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml).
Paths have no leading `/` and no `.git`.

```yaml
packhorse:
  dryRun:
    repositories:
      - "gitlab-org/gitaly"
      - "group/your-repo"
```

ArgoCD picks it up in about a minute. Don't also add the repo to `allowlist`,
because a repo in both lists gets cached.

## 3. Wait

Give it 24 hours for a busy repo and up to 72 hours for a quiet one, and make
sure it covers at least one full CI cycle.

The dry-run counters reset when a pod restarts. If that happens partway through,
start the wait again.

## 4. Read the dashboard

Open [Packhorse: Dry-run observations](https://dashboards.gitlab.net/d/packhorse-dryrun/packhorse3a-dry-run-observations?var-PROMETHEUS_DS=mimir-packhorse-main-gprd).
The **Per-repository summary** table has a row for each dry-run repo. The graphs
below it have a line per repo.

Two columns matter:

- **Would-hit rate** is `hit / (hit + miss + coalesce)`. It shows how often the
  cache would have had the answer, for the requests it's able to cache.
- **Upstream deflection** is `(hit + coalesce) / (hit + miss + coalesce + non-cacheable)`.
  It's the share of all the repo's traffic that would stay off Gitaly, and it's
  the number to decide on.

Most fetches also send an `ls-refs` request, which can't be cached. So it's
normal for about half the requests to be non-cacheable, and deflection tops out
at around half the hit rate.

Also check the **Disk pressure** row. `packhorse_dryrun_shadow_size_bytes` is
roughly how much disk the repo would use if promoted. That has to fit under
`maxCacheSize` with the repos already cached.

The table's colours don't match the thresholds below (it only goes green at 40%
deflection), so go by the numbers.

## 5. Decide

| Would-hit rate | Deflection | What to do |
| --- | --- | --- |
| 60% or more | 30% or more | [Promote it](#6-promote) |
| 60% or more | Under 30% | See [low deflection](#low-deflection) |
| 30% to 60% | Any | Keep watching for a full week. If it stays in this range, the repo's fetches probably don't repeat enough for caching to be worth it. |
| Under 30% | Any | See [low hit rate](#low-hit-rate), then [remove the repo](#remove-the-repo) |

### Low deflection

A high hit rate with low deflection means the cache works for the requests it
can serve, but most of the repo's traffic can't be cached.

- Compare `packhorse_dryrun_non_cacheable_total` with the other counters. If
  non-cacheable requests are well over half (say 70% or more), there's not much
  caching can do for this repo.
- Search the Packhorse logs for `component=simple_cached_git_fetch_handler` and
  the repo. The usual reasons a request can't be cached are shallow clones
  (`--depth=<N>`) and protocol features Packhorse doesn't support.
- Shallow clones usually come from the project's CI config. Ask the CI platform
  team if `GIT_DEPTH` can be raised or removed. If it can't, decide whether the
  part that can be cached is worth it.
- If one tool or client makes most of the requests (Bazel or a script, say),
  write that down with the decision. That way it's clear the low number comes
  from how the repo is used, not from the cache.

### Low hit rate

A low hit rate means the same fetches don't come in often enough for the cache
to serve them.

- Check the load is actually from fetches (`git-upload-pack`) and not pushes,
  LFS or the API. Packhorse only handles fetches.
- If every fetch asks for different objects, Packhorse can't help. Talk to the
  Gitaly team about other options, like tuning the pack-objects cache or moving
  the repo to a different storage.
- If the fetches should repeat but don't, look for CI config that makes each job
  fetch different refs, like dynamic branches or per-job SHAs. Fixing the CI
  config helps more than caching.

## 6. Promote

Open an MR to [`gitlab-com/gl-infra/argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps)
that moves the repo from `dryRun` to `allowlist` in
[`values.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml).

```yaml
packhorse:
  allowlist:
    repositories:
      - "gitlab-org/gitlab"
      - "group/your-repo"
  dryRun:
    repositories:
      - "gitlab-org/gitaly"
```

You don't need to touch [`gitlab-com/gl-infra/chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo)
again, since HAProxy already sends the repo to Packhorse.

After one CI cycle, check the
[Packhorse overview](https://dashboards.gitlab.net/d/packhorse-main/packhorse3a-overview?var-PROMETHEUS_DS=mimir-packhorse-main-gprd):

- `packhorse_cache_hits_total{repository="..."}` should be going up.
- `packhorse_cache_misses_total{repository="..."}` should be close to what
  `would_miss` was during dry-run.
- `packhorse_errors_total{repository="..."}` shouldn't be going up.

If CI jobs start failing for the repo, see
[CI jobs are failing for a repo cached by Packhorse](packhorse.md#ci-jobs-are-failing-for-a-repo-cached-by-packhorse).

## Remove the repo

If you decide not to promote the repo, undo both changes. Remove it from
`packhorse.dryRun.repositories` in
[`gitlab-com/gl-infra/argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps)
and from `packhorse_repos` in
[`gitlab-com/gl-infra/chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo).
Its traffic then goes straight to Gitaly again.

## Troubleshooting

### The repo doesn't show up on the dashboard

The chef MR is missing or hasn't rolled out yet. Run
`grep <repo> /etc/haproxy/haproxy.cfg` on a `haproxy-ci` host to check.

### Every panel says "No data"

The `PROMETHEUS_DS` variable at the top left is set to the wrong datasource.
Set it to `mimir-packhorse-main-gprd`.

### Only the non-cacheable counter goes up

The repo's traffic is all shallow clones or uses protocol features Packhorse
doesn't support. Check the User-Agents in the Packhorse logs.

### The repo shows up in the "Cache-path guardrail" panel during dry-run

The repo is in both `allowlist` and `dryRun`, so it's being cached. Remove it
from `allowlist` in the
[ArgoCD values file](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/packhorse/env/gprd/clusters/packhorse-main-gprd/values.yaml).

### `packhorse_errors_total` goes up after promotion

The cache disk might be full, or requests might be queuing up behind the same
fetch. Compare `packhorse_cache_size_bytes` with `packhorse_cache_max_size_bytes`,
and see
[Packhorse on-disk cache size is saturated](packhorse.md#packhorse-on-disk-cache-size-is-saturated).

## GitLab Dedicated

Packhorse isn't on Dedicated yet. When it ships there, the two lists become
per-tenant fields in the tenant model, and Envoy Gateway in the tenant's EKS
cluster decides routing instead of HAProxy. The work is tracked in
[gl-infra&2082](https://gitlab.com/groups/gitlab-com/gl-infra/-/work_items/2082).
