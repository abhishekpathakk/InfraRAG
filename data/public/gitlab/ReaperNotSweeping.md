# ReaperNotSweeping

The [reaper](https://gitlab.com/gitlab-com/gl-infra/reaper) deletes orphaned ephemeral VMs in the runner projects. It sweeps every 10 minutes and sets `reaper_last_sweep_timestamp_seconds` when a sweep completes. This alert fires when no sweep has completed for 30 minutes, or the metric is gone.

## Impact

Orphaned VMs (stale heartbeat, stopped, or unlabeled and old) are not deleted while the reaper is down. Nothing else depends on it. Left long enough, leaked VMs count against instance and disk quotas in the affected projects.

## What to check

1. The pod: `kubectl -n reaper get pods` on `runner-managers-gprd-1`. It is a single-replica Deployment; ArgoCD manages it from `services/reaper` in [argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps).
2. Its logs. A sweep that never finishes is a list call that hangs; each compute API call has a 10s deadline, so that should not last. Config errors show at startup as `loading config` or `resolving policies`.
3. If the metric is absent but the pod is fine, the PodMonitor or Prometheus: the PodMonitor needs `release: k8s-monitoring-stack`.

## Resolution

Restart the pod if it is stuck. If a config change broke it, revert in argocd/apps. There is no manual cleanup to do: the next sweep picks up whatever accumulated.
