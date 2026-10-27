# Troubleshooting `data-server-rebuild-ansible` Pipeline Failures

The [`data-server-rebuild-ansible`](https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible)
pipeline periodically rebuilds the Patroni "data analytics" replica VMs in the
`gitlab-db-benchmarking` GCP project from fresh production snapshots. Each
shard (`main`, `ci`, `sec`, `test`) refreshes the data disk on a corresponding
`patroni-*-data-analytics-01-db-db-benchmarking` VM in `us-east1-c` and is
then promoted out of standby so analytics queries hit recent-ish data.

These are internal data-analytics replicas, not customer-facing. Failures
typically map to severity-4 and do not affect production traffic. There is no
alerting tied to this pipeline; incidents are filed manually after a failed
pipeline is noticed.

## Mental Model

The pipeline runs three playbooks in order, against a target VM that is
expected to be **already running**:

| Stage         | Playbook              | Where it runs  | What it does                                                                          |
| ------------- | --------------------- | -------------- | ------------------------------------------------------------------------------------- |
| `replacedisk` | `disableservices.yml` | on the VM      | Wait for SSH (1200s timeout), stop patroni/pgbouncer                                  |
| `replacedisk` | `gcpdiskreplace.yml`  | on `localhost` | Stop VM, detach `…-data` disk, delete it, create from snapshot, attach, start VM      |
| `postscript`  | `rebuild.yml`         | on the VM      | Wait for SSH, reset patroni state, start postgres, promote out of standby             |

Only `gcpdiskreplace.yml` ever stops or starts the VM. No playbook is designed
to cold-start a VM that is already `TERMINATED` when the pipeline begins.
`disableservices.yml`'s first task is `wait_for` on port 22 with a 1200s
(20-minute) timeout, so if the VM is off, every retry waits 20 minutes before
the pipeline gives up.

The shard-to-VM and shard-to-source-snapshot mappings live in
[`vars.yml`](https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible/-/blob/main/vars.yml)
under `instance_names:` and `snapshot_source_disks:`. Look them up directly
rather than relying on a copy here:

```sh
# From a checkout of data-server-rebuild-ansible:
yq '.instance_names, .snapshot_source_disks' vars.yml
```

## Symptoms

Common error messages in the failing job log, mapped to a cause section
below:

* `Timeout when waiting for search string OpenSSH in <hostname>:22` — the
  20-minute SSH wait failed (cold-start; see [Target VM is TERMINATED](#target-vm-is-terminated-at-pipeline-start)).
* `Target GCE VM '…' is in state 'TERMINATED' (expected: RUNNING)` —
  preflight refusing to wait for SSH (same cause; the fast-fail variant
  after [MR !100][mr-100]).
* `Invalid value for field 'resource.sizeGb': 'XXX'. Requested disk size
  cannot be smaller than the snapshot size (YYY GB)` — `vars.yml` size
  mismatch (see [Disk size smaller than snapshot](#disk-size-smaller-than-snapshot)).
* `Could not translate host name "master.patroni.service.consul" to
  address` — patroni stuck trying to reach a deleted primary (see
  [Patroni stuck on standby's missing primary DNS](#patroni-stuck-on-standbys-missing-primary-dns)).
* WAL-replay timeout from `wait for "<host>" startup scripts to finish` —
  see [Other failure modes](#other-failure-modes).

## Target VM is TERMINATED at pipeline start

This is the most common case. The VM was previously stopped (a manual
action, a failed prior pipeline mid-flight, GCP maintenance, or zone
resource exhaustion at the moment of start) and nothing has restarted it
since. The playbook then sits at `wait for host to be up` for 20 minutes
per attempt.

For a recent example see the production incident
[gitlab-com/gl-infra/production#21938](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21938).

### Identify

```sh
gcloud --project=gitlab-db-benchmarking compute instances describe \
  <instance-name> --zone=us-east1-c \
  --format='value(status,lastStartTimestamp,lastStopTimestamp)'
```

If `status` is `TERMINATED` (or `STOPPING`/`STAGING`), this is the cause.

### Resolution

Start the VM and re-run the failing job:

```sh
gcloud --project=gitlab-db-benchmarking compute instances start \
  <instance-name> --zone=us-east1-c
```

The boot disk and `…-log` disk persist across stops; only `…-data` is
recreated by the pipeline. Starting the VM is non-destructive: its old data
disk (if still attached) will be wiped and replaced as part of
`gcpdiskreplace.yml`.

After the VM reaches `RUNNING`, retry the failing pipeline job. The
`replacedisk` stage will pick up where it left off; `gcpdiskreplace.yml`'s
detach/delete steps are idempotent (`failed_when` guards on `"is not
attached to instance"` and `"was not found"`).

**NOTE:** Retrying the failing job alone will not start the VM. The
pipeline has no logic to start a `TERMINATED` VM, so each retry hits the
same 1200s SSH timeout until the VM is up.

## Disk size smaller than snapshot

GCE refuses to create a disk smaller than its source snapshot. If
production disks are resized but `vars.yml` is not updated for every shard
that sources from them, the next rebuild fails at the
`create "<instance>-data" disk` task with:

```
ERROR: (gcloud.compute.disks.create) Could not fetch resource:
 - Invalid value for field 'resource.sizeGb': 'XXX'.
   Requested disk size cannot be smaller than the snapshot size (YYY GB)
```

### Identify

Compare `snapshot_source_disk_size[shard]` in `vars.yml` to the actual
source snapshot size:

```sh
# Find the source snapshot the pipeline uses
SOURCE_DISK="$(yq '.snapshot_source_disks.<shard>' vars.yml)"  # e.g. patroni-sec-v17-02-db-gprd

# Get the latest READY snapshot for that source disk
gcloud compute snapshots list --project=gitlab-production \
  --filter="status~READY AND sourceDisk~${SOURCE_DISK}" \
  --sort-by=~creationTimestamp --limit=1 \
  --format='value(name,diskSizeGb)'
```

If the snapshot's `diskSizeGb` exceeds the configured shard size in
`vars.yml`, this is the cause.

**NOTE:** `test` shard sources from `sec`'s gprd disk, so resizing `sec`
requires bumping both `sec` and `test` entries in `vars.yml`.

### Resolution

1. Open an MR bumping the affected shard's
   `snapshot_source_disk_size[<shard>]` to match (or exceed) the snapshot
   size. See [MR !101][mr-101] for an example.
2. Merge and re-run the pipeline.

**IMPORTANT:** If `create` failed, the pipeline already ran `stop`,
`detach`, and `delete`. The VM is now `TERMINATED` and its `…-data` disk is
gone. Re-running the failing `replacedisk` job specifically will succeed
past those steps (idempotent guards) and create the new disk at the
corrected size. Do not re-run the whole pipeline from
`disableservices.yml`: the VM will still be `TERMINATED` until
`gcpdiskreplace.yml`'s final `start` step, so a re-run from the top would
immediately hit the `TERMINATED VM` cause above.

## Patroni stuck on standby's missing primary DNS

A snapshot taken from a standby cluster may reference a primary
(`master.patroni.service.consul`) that does not exist in `db-benchmarking`
DNS. Postgres fails to start and patroni restarts it in a tight loop until
`monitoring until ready` times out.

`rebuild.yml` already handles this by promoting out of standby
(`gitlab-patronictl edit-config -s standby_cluster=null --force`). If that
promotion task itself fails, run it manually on the target VM:

```sh
ssh data-analytics-refresh@<instance>.c.gitlab-db-benchmarking.internal \
  "sudo gitlab-patronictl edit-config -s standby_cluster=null --force"
```

Then re-run the `ansible-deploy` job to continue from `wait for "<host>"
state to be running`.

## Other failure modes

Less common, but historically observed:

* **`ZONE_RESOURCE_POOL_EXHAUSTED`** on `start`: wait for capacity to free,
  or retry. To list recent occurrences in the audit log:

  ```sh
  gcloud logging read \
    'protoPayload.status.message="ZONE_RESOURCE_POOL_EXHAUSTED" AND protoPayload.methodName="v1.compute.instances.start"' \
    --project=gitlab-db-benchmarking --freshness=30d --limit=20 \
    --format='value(timestamp,protoPayload.resourceName)'
  ```

* **WAL-replay timeout** during `monitoring until ready`: Postgres is
  replaying a large amount of WAL after restoring from snapshot. Bump
  `patroni_ready_timeout[<shard>]` in `vars.yml` if persistent, or wait it
  out and retry.

* **Snapshot not READY**: the `wait for snapshot to be ready` task retries
  30× at 60s. If a snapshot is still being taken in production this can
  happen; usually self-resolves on retry.

## Useful commands

List all rebuild VMs and their current state:

```sh
gcloud compute instances list --project=gitlab-db-benchmarking \
  --filter="name~analytics-01-db-db-benchmarking" \
  --format="table(name,zone,status,lastStartTimestamp)"
```

## Reference

* Pipeline source: <https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible>
* `vars.yml`: <https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible/-/blob/main/vars.yml>
* Pipeline schedules: <https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible/-/pipeline_schedules>

[mr-100]: https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible/-/merge_requests/100
[mr-101]: https://gitlab.com/gitlab-com/gl-infra/data-server-rebuild-ansible/-/merge_requests/101
