# ReaperBudgetRefusal

The reaper deletes instances whose `runner_manager_heartbeat` label is more than 4 hours old. As a guard against a broken heartbeat writer, it refuses to delete when more than 25% of the heartbeating instances in a project are stale in one sweep, and reports them instead. This alert fires when that happened.

## Impact

None immediately: the reaper stopped itself. The question is why so many instances in one project stopped getting heartbeats.

## What to check

1. The managers for that project: `kubectl -n gitlab-runner get pods -l shard=<shard>`. Dead or crash-looping managers stop writing heartbeats for their VMs; those VMs are real orphans and the refusal is a false positive of the budget.
2. If the managers are healthy, their logs for `update-labels` errors. A docker-machine or IAM problem that stops label writes makes every VM look stale; the refusal is doing its job and nothing should be deleted.
3. The reaper log line `refusing heartbeat deletions` has the stale and labeled counts.

## Resolution

If the managers are dead: fix or restart them. Once running they heartbeat their own VMs again; VMs from previous manager instances stay stale and the reaper deletes them once the stale fraction drops below the budget, or by hand with `gcloud compute instances delete` after checking the census (`gcloud compute instances list --project <p> --filter='labels.runner_manager_heartbeat:*' --sort-by=labels.runner_manager_heartbeat`).

If the heartbeat writer is broken: fix that first. Do not raise the budget.
