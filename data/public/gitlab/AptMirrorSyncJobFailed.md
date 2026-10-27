# AptMirrorSyncJobFailed

## Overview

A sync job for the internal apt mirror failed. See
[the apt mirror runbook](../README.md).

Nothing breaks immediately. The mirror keeps serving every package it already
holds, so `apt-get update` and installs carry on working. What has stopped is
taking in new upstream content — including the versions a rollback would need,
which is the reason the mirror exists.

The alert counts only jobs started in the last 24 hours, so it clears on its own
once a failed job ages out. How long the Job object itself sticks around depends
on which job failed: a CronJob run (`apt-mirror-resync-*`) is kept until three
more failures evict it, while the PostSync job (`apt-mirror-sync`) carries
`hook-delete-policy: BeforeHookCreation` and is deleted when ArgoCD next syncs
the app.

## Services

- [Service Overview](../README.md)
- Owner: Production Engineering: Fleet Management
- Alerts channel: `#f_fleet_alerts`

## Diagnosis

```shell
glsh kube use-cluster gprd   # or gstg
kubectl -n apt-mirror get job
kubectl -n apt-mirror logs job/<job_name>
```

The `job_name` label on the alert names the job. `apt-mirror-sync` is the
PostSync job that runs on an ArgoCD sync; `apt-mirror-resync-*` are the daily
CronJob's runs.

The script reconciles remotes, repositories and distributions through the Pulp
REST API and then syncs and publishes, so read the logs for which step failed.
The usual causes:

- an upstream repository unreachable, or its suite or components renamed, which
  shows as a sync task failure for one repository
- the Pulp API unavailable, in which case `AptMirrorContentUnavailable` is
  probably firing too
- a signing failure, which leaves a publication unsigned rather than failing
  outright — see the signing note in the runbook

## Remediation

- Re-run it. The script is idempotent: it `PATCH`es existing remotes rather than
  recreating them.

  ```shell
  kubectl -n apt-mirror create job --from=cronjob/apt-mirror-resync manual-resync
  ```

- If a repository's upstream metadata changed, fix the entry in
  `services/apt-mirror/env/<env>/values-apt-repos.yaml` and check it against the
  upstream `Release` file before merging. A component upstream does not declare
  cannot be mirrored.
- Confirm recovery by checking the repository publishes, rather than by the job
  exiting zero:

  ```shell
  curl -sL <content-url>/dists/<distribution>/InRelease | head -3
  ```

  A good publication starts with `-----BEGIN PGP SIGNED MESSAGE-----`.
