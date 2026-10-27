# AptMirrorSyncStale

## Overview

No sync job for the internal apt mirror has completed in 36 hours. See
[the apt mirror runbook](../README.md).

The re-sync CronJob runs daily at 03:17 UTC, so this means at least two runs
have not landed. Either the CronJob has stopped being scheduled, or its jobs
start and never complete. `AptMirrorSyncJobFailed` covers jobs that fail
outright, so this one is the case where nothing is failing because nothing is
running.

As with a failed sync, the mirror keeps serving what it holds. What it no longer
does is pick up new upstream versions.

## Services

- [Service Overview](../README.md)
- Owner: Production Engineering: Fleet Management
- Alerts channel: `#f_fleet_alerts`

## Diagnosis

```shell
glsh kube use-cluster gprd   # or gstg
kubectl -n apt-mirror get cronjob apt-mirror-resync
kubectl -n apt-mirror get job --sort-by=.status.startTime
kubectl -n apt-mirror describe cronjob apt-mirror-resync
```

Three things to separate:

- **Suspended.** `SUSPEND` is `True` in the CronJob output, so nothing is being
  scheduled.
- **Not scheduled.** `LAST SCHEDULE` is old while `SUSPEND` is `False` — check
  the events in `describe`, and whether the app still exists in ArgoCD.
- **Never completing.** Jobs exist with recent start times but no completion.
  Read their pod logs; a sync that hangs is usually waiting on an unreachable
  upstream.

## Remediation

- If it is suspended, unsuspend it, then look for why it was suspended before
  assuming that is the fix:

  ```shell
  kubectl -n apt-mirror patch cronjob apt-mirror-resync -p '{"spec":{"suspend":false}}'
  ```

- If the CronJob is missing or altered, reconcile the app in ArgoCD — it is
  managed from
  [`services/apt-mirror/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/apt-mirror),
  not by hand.
- Trigger a run without waiting for the schedule:

  ```shell
  kubectl -n apt-mirror create job --from=cronjob/apt-mirror-resync manual-resync
  ```

- The alert clears once a job completes, since it measures the newest completion
  time.
