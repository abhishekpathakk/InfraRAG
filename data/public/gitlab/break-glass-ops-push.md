# Break-glass: Deploying chef-repo changes via ops.gitlab.net during a high-severity incident

Use this procedure **only** when GitLab.com CI is broken or unavailable and you need to deploy
a Chef change urgently (severity::1 or severity::2 incident).

Normally, chef-repo changes are merged on [gitlab.com/gitlab-com/gl-infra/chef-repo] and
automatically mirrored to [ops.gitlab.net/gitlab-com/gl-infra/chef-repo] via a push mirror.
The ops mirror runs the Chef apply pipeline on every push to `master`. In an emergency you can
open a merge request directly on the ops mirror, bypassing the broken GitLab.com CI path.

## When to use this

- Active sev::1 or sev::2 incident where gitlab.com CI is unavailable or broken
- The fix requires a Chef change
- Normal merge-via-CI path on gitlab.com is blocked

Do **not** use this for routine changes. The ops mirror is normally read-only to ensure
gitlab.com stays the source of truth.

## Prerequisites

- **Owner** access on `ops.gitlab.net/gitlab-com/gl-infra/chef-repo` (required to temporarily
  enable merge requests on the project). If you do not have Owner access, use the shared
  **`ops-gitlab-net admin`** account in 1Password.
- Your local `chef-repo` clone with the ops remote configured (see step 1)

## Steps

### 1. Configure the ops remote (if not already done)

```bash
cd ~/path/to/chef-repo
git remote add ops git@ops.gitlab.net:gitlab-com/gl-infra/chef-repo.git
git fetch ops
```

### 2. Create your fix branch from the current ops master

```bash
git fetch ops
git checkout -b emergency-fix-<incident-id> ops/master

# Make your change, then:
git add -A
git commit -m "Emergency fix: <brief description> (INC-XXXXX)"
git push ops emergency-fix-<incident-id>
```

### 3. Disable the push mirror

The push mirror will push gitlab.com `master` to ops on its next scheduled run, silently
reverting your emergency fix if the canonical MR hasn't merged yet. Disable it now via the
API to avoid that race condition:

```bash
# Look up the current mirror ID (in case it changed since this runbook was written)
MIRROR_ID=$(curl --silent --header "PRIVATE-TOKEN: <your-gitlab-com-token>" \
  "https://gitlab.com/api/v4/projects/gitlab-com%2Fgl-infra%2Fchef-repo/remote_mirrors" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

curl --request PUT --header "PRIVATE-TOKEN: <your-gitlab-com-token>" \
  --header "Content-Type: application/json" \
  --data '{"enabled": false}' \
  "https://gitlab.com/api/v4/projects/gitlab-com%2Fgl-infra%2Fchef-repo/remote_mirrors/${MIRROR_ID}"
```

### 4. Temporarily enable merge requests on the ops mirror

MRs are disabled on the ops mirror under normal circumstances. As an Owner, temporarily
re-enable them via the GitLab UI:

1. Go to [chef-repo project settings](https://ops.gitlab.net/gitlab-com/gl-infra/chef-repo/edit#js-shared-permissions)
2. Under **Visibility, project features, permissions**, enable **Merge requests**
3. Save changes

### 5. Open and merge the MR on ops

1. Open an MR from your branch to `master` on the ops project
2. Since this is an emergency, self-merge is acceptable — but document it in the incident
   timeline immediately
3. Merging to `master` triggers the CI pipeline which runs:
   - `apply:staging` — applies to staging first
   - `apply:production` — applies to production (only runs after staging succeeds and for
     production-scoped file changes)

> [!WARNING]
> This bypasses the normal gitlab.com review process. Keep the change minimal and document
> everything in the incident timeline.

### 6. Monitor the pipeline

Watch the [chef-repo pipelines](https://ops.gitlab.net/gitlab-com/gl-infra/chef-repo/-/pipelines)

The `apply::production` job only triggers if your change touches
[production-scoped paths](https://ops.gitlab.net/gitlab-com/gl-infra/chef-repo/-/blob/master/.gitlab-ci.yml)
(e.g. `roles/gprd*`, `environments/gprd.json`, `environments/ci.json`, etc.).
If your change is production-scoped and the job does not appear, check that `CHEF_APPLIER_KEY`
is set on the ops project.

### 7. Re-disable merge requests on the ops mirror

Once your MR is merged, revert the project setting:

1. Go to [chef-repo project settings](https://ops.gitlab.net/gitlab-com/gl-infra/chef-repo/edit#js-shared-permissions)
2. Disable **Merge requests** again
3. Save changes

### 8. Reconcile with gitlab.com canonical repo (ASAP after incident)

The push mirror does **not** propagate changes backwards from ops to gitlab.com. Open a
proper MR on the canonical repo with the same change:

```bash
git push origin emergency-fix-<incident-id>
# Open MR via gitlab.com UI or: glab mr create --source-branch emergency-fix-<incident-id>
```

Once the canonical MR is merged, re-enable the push mirror:

```bash
curl --request PUT --header "PRIVATE-TOKEN: <your-gitlab-com-token>" \
  --header "Content-Type: application/json" \
  --data '{"enabled": true}' \
  "https://gitlab.com/api/v4/projects/gitlab-com%2Fgl-infra%2Fchef-repo/remote_mirrors/${MIRROR_ID}"
```

> [!IMPORTANT]
> Do not leave the mirror paused indefinitely. Re-enable it as soon as the canonical MR
> is merged so the ops mirror stays in sync going forward.

## After the incident

- Open a follow-up issue documenting what was pushed, when, and by whom
- Ensure the canonical MR is merged and the mirror is back in sync
- Re-disable MRs on the ops project if not already done
- If the procedure revealed any gaps, update this runbook

## Related links

- [chef-repo on gitlab.com](https://gitlab.com/gitlab-com/gl-infra/chef-repo) — canonical source
- [chef-repo on ops.gitlab.net](https://ops.gitlab.net/gitlab-com/gl-infra/chef-repo) — ops mirror (pipelines run here)
- [infra-mgmt: chef Terraform environment](https://gitlab.com/gitlab-com/gl-infra/infra-mgmt/-/tree/master/environments/chef)
- [INC-10792 incident review](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22260) — the incident that prompted this runbook
- [Corrective action: break-glass deploy path](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29170)
