# Gitaly Snapshot Verification

## Symptoms

### `GitalySnapshotVerificationDelayed` is fired

When this alert is fired, it means that no verification pipeline was able to complete successfully. More precisely, the `report` job
wasn't able to complete or it couldn't publish the metrics properly.

#### Troubleshooting

Check the scheduled pipelines in [verification project](https://ops.gitlab.net/gitlab-com/gl-infra/data-access/durability/gitlab-restore/gitaly-snapshot-verification/-/pipelines),
see if there are any failures in the first 3 stages:

* For the `restore` stage, errors would be mostly GCP-related. Check the service account used for restoring the snapshots, or if there any quotas being hit.
* For the `verify` stage, errors could be related to SSH-ing into the machine. Check if the restored machine is reachable by `gcloud compute ssh ...`.
* For the `report` stage, errors could be related to SSH-ing into the machine or hitting blackbox endpoint is failing for some reason. Check if the Ops blackbox instance is reachable from the runner.
* In general, the first 3 stages depend on Vault running successfully to get the required tokens. Check if the correct permissions are in place.

### `GitalySnapshotVerificationNoRecentChanges` is fired

This alert means a verification pipeline found no repository that has a recent commit. Take note of the Gitaly instance and its project name for which this alert was fired.

#### Troubleshooting

1. The Gitaly instance could be a low-traffic one that just didn't receive any new writes in the previous day. Try triggering a new pipeline for it using these [instructions](https://ops.gitlab.net/gitlab-com/gl-infra/data-access/durability/gitlab-restore/gitaly-snapshot-verification#verifying-specific-project-andor-instance).
1. The Gitaly instance may not have a recent snapshot created. Track the most recent pipeline for this instance and find the name of the snapshot used in the logs of the `restore` job. See if it's really recent or a stale snapshot.
    * If it's a stale one, then there's a problem with the scheduled snapshotting that needs addressing.
1. Trigger a new verification pipeline for the Gitaly instance [instructions](https://ops.gitlab.net/gitlab-com/gl-infra/data-access/durability/gitlab-restore/gitaly-snapshot-verification#verifying-specific-project-andor-instance). After the `verify` is finished, trying SSH-ing into the machine and check if the verification script is running (using `ps`) and there are lines being printed in `/var/tmp/git-report.log`.
    * If not, trying running the [script](https://ops.gitlab.net/gitlab-com/gl-infra/data-access/durability/gitlab-restore/gitaly-snapshot-verification/-/blob/50aecbacb5d1b9b18fc3a50caaa82983e1d27d32/verify.yml#L71-79) (the highlighted lines only) yourself and note any errors.
