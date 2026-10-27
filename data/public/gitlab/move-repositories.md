# Moving repositories from one Gitaly node to another

A GitLab Project will have a git repository associated with it which is hosted on a Gitaly node. This can be moved from 1 Gitaly node to another for whatever reason.

## Single Repository

When you want to move a single repository to another Gitaly node we have [glsh
gitaly](https://gitlab.com/gitlab-com/runbooks#running-helper-scripts-from-runbook)
a command where you specify the project and it will move the git repository
for that project to another Gitaly node. The process will ask for an Administrator
Personal Access Token (PAT) with `api` permissions.

```shell
glsh gitaly repositories move -e <ENVIRONMENT> -d <DESTINATION_STORAGE> <PROJECT_ID>
```

The move is a production change. Open a change request from the
[`change_management` template](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/new?issuable_template=change_management)
in `gitlab-com/gl-infra/production` and record the console output of each step
there. For a worked example see
[production#23079](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23079).

### Prerequisites

- A checkout of this repository, so that `glsh` is on your `PATH`.
- An admin PAT with the `api` scope. The script prompts for it every run and
  never reads it from an environment variable. Revoke it afterwards.
- Rails console access to the target environment.

### Arguments

- `-e` is `gstg` or `gprd`.
- `-d` is the destination storage, the node's FQDN. Optional. Without it Rails
  picks a storage by weight, so pass it when relieving a specific node. List
  valid names with `glsh gitaly storages list -e <ENVIRONMENT>`.
- `<PROJECT_ID>` also accepts a full path. Several projects can be listed.

Example:

```shell
glsh gitaly repositories move -e gprd -d gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-2650.internal <PROJECT_ID>
```

### Move states

The move record's `state` column is an integer. The console snippets below use
`human_state_name` so you see the word, but the API and some logs show the
number.

| Value | Name             | Meaning                                                      |
| ----- | ---------------- | ------------------------------------------------------------ |
| 1     | `initial`        | Record created, job not yet scheduled                        |
| 2     | `scheduled`      | Sidekiq job queued                                           |
| 3     | `started`        | Copying, project is read-only                                |
| 6     | `replicated`     | Copy done, database updated, deleting the source copy        |
| 4     | `finished`       | Done                                                         |
| 5     | `failed`         | Failed before or during the copy, project is on the source   |
| 7     | `cleanup_failed` | Project is on the destination, source copy not deleted       |

### Pre-move checks

Run these read-only checks in a Rails console before scheduling the move. They
take a minute and catch the two failures we have hit in production.

```ruby
project = Project.find_by_full_path('<group/project>')
project.id
project.repository_storage              # the source storage
project.repository_read_only            # must be nil or false
project.statistics&.repository_size     # bytes, sets expectations for duration
project.repository_storage_moves.order(id: :desc).limit(3).map { |m| [m.id, m.human_state_name, m.destination_storage_name, m.error_message] }
```

If the last line shows a move in state `scheduled` or `started`, do not schedule
another one. Wait for it to finish or fail first.

If the project has forks it is the source of an object pool. The move copies the
pool before the repository and reads the pool's storage from the
`pool_repositories` row, not from the project. Check that row points at a
storage that exists and matches the project:

```ruby
pool = project.pool_repository
pool && [pool.id, pool.shard.name, pool.state, pool.disk_path]
pool && pool.shard.name == project.repository_storage   # must be true
```

If the shard name is a storage that no longer exists (an `nfs-file` name, for
example) or the last line is `false`, stop and follow
[Stale object pool shard](#stale-object-pool-shard) before moving.

Check capacity on both nodes before you start. The
[Gitaly rebalancing dashboard](https://dashboards.gitlab.net/d/gitaly-rebalancing/gitaly-rebalance-dashboard?orgId=1)
shows disk usage per storage. The destination must have room for the repository,
its wiki, and a copy of the object pool if the project has one.

### Running the move

```shell
glsh gitaly repositories move -e <ENVIRONMENT> -d <DESTINATION_STORAGE> <PROJECT_ID>
```

The script asks for the admin PAT, then schedules the move through the
[repository storage moves API](https://docs.gitlab.com/api/project_repository_storage_moves/)
and polls the move state once a second for up to an hour. Normal output walks
through `scheduled`, `started`, `replicated` and ends with `finished`.

When moving a repository, it sets it to read-only so write requests will start
failing, it's good to look at the read/write distribution of a project to
better understand the impact, for example below we see the top 20 RPCs for the
`gitlab-org/gitlab` repository and we can see most requests are read
requests.

![rpc by project](./img/rpc-by-project.png)

[source]( https://log.gprd.gitlab.net/goto/b42f7da0-7a35-11ed-85ed-e7557b0a598c)

### Monitoring the move

- The Sidekiq job is `Projects::UpdateRepositoryStorageWorker`. In Kibana use
  the `pubsub-sidekiq-inf-gprd*` index pattern and filter on
  `json.class: Projects::UpdateRepositoryStorageWorker` and the project path.
  A failed move logs the exception message there.
- The move record keeps the reason for a failure. From the console:

  ```ruby
  Project.find(<PROJECT_ID>).repository_storage_moves.order(id: :desc).first.then { |m| [m.human_state_name, m.source_storage_name, m.destination_storage_name, m.error_message] }
  ```

- Watch the source and destination nodes on the
  [Gitaly host detail dashboard](https://dashboards.gitlab.net/d/gitaly-host-detail/gitaly-host-detail?orgId=1&var-environment=gprd).
  Replication adds read load on the source and write load on the destination
  for the duration of the copy.

### Post-move verification

```ruby
project = Project.find(<PROJECT_ID>)
project.repository_storage               # the destination storage
project.repository_read_only             # nil or false
project.repository_storage_moves.order(id: :desc).first.human_state_name   # "finished"
project.repository.exists?               # true
project.pool_repository&.shard&.name     # equals repository_storage when the project has a pool
```

Then confirm the project loads in the browser and that a push to a scratch
branch succeeds if the project is one we control.

### When the move fails

The script exits with
`Error moving project <url>, got unexpected state: <state>, aborting!` as soon
as the move record leaves the normal states. The state will be `failed` or
`cleanup_failed`. The service wraps the whole copy in a rescue that records the
error message on the move record and marks it failed. See
[`update_repository_storage_methods.rb`](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/services/concerns/update_repository_storage_methods.rb).

Do this, in order:

1. Read the error. Use the console one-liner in [Monitoring the move](#monitoring-the-move)
   or the Kibana filter. Paste the message into the change request.
2. Check where the project is. Compare `project.repository_storage` with the
   move's `destination_storage_name`. A failure during the copy leaves the
   project on the source. A failure after the copy, or an interruption, can
   leave it on the destination. The cases below say which applies.
3. Check the project is writable again. The `failed` and `cleanup_failed`
   transitions set `repository_read_only` back to `false`, but confirm it, and
   if the project is still read-only use the fix under
   [Repository left read-only](#repository-left-read-only).
4. Match the message against the cases below. If none fit, stop and ask in
   `#g_gitaly` before retrying. An unexplained failure is not safe to retry
   blind.
5. A retry is a new move. Once the cause is fixed, run the same `glsh` command
   again. Do not attempt to resume or edit the failed move record.

#### Stale object pool shard

Symptom. The move fails within seconds and the error message is
`storage not found: "<old storage name>"` for a storage that is not the source
or the destination, typically an `nfs-fileNN` name from a decommissioned shard.
The project is still on the source.

Cause. The project has forks, so it has an object pool. The `pool_repositories`
row the project points at names a shard that is no longer in the Rails config.
Day to day reads work because the project's own `repository_storage` is correct,
but the move copies the pool first and fails when it asks Gitaly for a storage
Rails does not know. Projects that lived on the old NFS shards and have forks
are the ones most likely to be affected.

Diagnose, read-only:

```ruby
project = Project.find(<PROJECT_ID>)
pool = project.pool_repository          # nil means no pool, this section does not apply
pool && [pool.id, pool.shard.name, pool.state]
pool && PoolRepository.where(disk_path: pool.disk_path).map { |p| [p.id, p.shard.name, p.state] }
```

Usually there is a second `PoolRepository` row with the same `disk_path` whose
shard matches `project.repository_storage` and whose state is `ready`. That is
the row the project should be using.

Fix. This is a production database write on a row shared with every fork, so
record it in the change request and have a Gitaly engineer confirm the pool IDs
before running it. Point the project at the correct row, then relink:

```ruby
project = Project.find(<PROJECT_ID>)
old_pool_id = project.pool_repository.id   # note it for rollback
good_pool = PoolRepository.by_disk_path_and_shard_name(project.pool_repository.disk_path, project.repository_storage).take
good_pool.nil?                       # must be false, otherwise stop
good_pool.state                      # must be "ready", otherwise stop
project.update!(pool_repository: good_pool)
project.link_pool_repository
```

Then re-run the `glsh` move.

Rollback. `project.update!(pool_repository_id: <OLD_POOL_ID>)` restores the
database pointer. It does not undo the `link_pool_repository` call, which told
Gitaly to point the repository's alternates at the good pool. Both pools have
the same disk path on the same storage, so the on-disk link is unchanged in
practice, but say so in the change request. Leave the stale row in place. Other
forks may still reference it and it does no harm until a move touches it.

If `good_pool` is `nil`, stop. The pool is missing or on another node and
rebuilding it is a different change that needs Gitaly review.

#### Repository storage move was interrupted

Symptom. The error message is `Repository storage move was interrupted`.

Cause. Sidekiq restarted while the move was in `started`. The service marks the
move failed on the next run instead of resuming it.

Fix. First find out how far it got. Compare `project.repository_storage` with
the move's `destination_storage_name`. If they differ, the copy did not
complete and a retry is safe. If they match, the database was already updated
and the repository is on the destination. In that case verify the repository
with the [post-move verification](#post-move-verification) steps and do not
schedule another move. If anything looks inconsistent, ask `#g_gitaly`.

#### Repository left read-only

Symptom. The move failed and `project.repository_read_only` is still `true`.
Pushes fail with a read-only message.

Cause. Tracked in [gitlab#385309](https://gitlab.com/gitlab-org/gitlab/-/issues/385309).

Fix. Confirm the move is not in state `scheduled` or `started`, then:

```ruby
Project.find(<PROJECT_ID>).update!(repository_read_only: false)
```

#### Timeout waiting for pushes

Symptom. The error message is `Timeout waiting for project repository pushes`
or the wiki or design equivalent. The project is still on the source.

Cause. The service waits up to 30 seconds for in-flight pushes to drain before
copying. A busy repository can keep it above zero.

Fix. Retry during a quieter window for that project. Nothing was copied.

#### Checksum mismatch or Gitaly error during replication

Symptom. The error message is
`Failed to verify project repository checksum from <old> to <new>`, or names
a gRPC deadline or `ReplicateRepository`. The project is still on the source.

Cause. Gitaly raised the error mid-copy. The source repository is intact. The
service deletes the partial copy on the destination before recording the
failure.

Fix. Retry once. If it fails the same way twice, stop and ask `#g_gitaly`. If
the destination still shows the repository after a failure, ask `#g_gitaly`
before deleting anything.

#### Move finished but cleanup failed

Symptom. The script exits with `got unexpected state: cleanup_failed`. The
project is on the destination and writable.

Cause. Replication and the database update succeeded but deleting the source
copy did not.

Fix. No user impact. The source copy may still be at its original path on the
source node and only costs disk. Confirm with
`Gitlab::Git::Repository.new('<SOURCE_STORAGE>', "#{project.disk_path}.git", nil, nil).exists?`
and agree its removal with `#g_gitaly`. Do not re-run the move.

#### The glsh script timed out

Symptom.
`Timeout waiting for the move to succeed for project <url>, aborting! Note that the move will continue running in the background.`
after about an hour.

Cause. The script stops polling, the Sidekiq job does not. Very large
repositories can take longer than an hour.

Fix. Keep watching the move record from the console until it reaches
`finished`, `failed` or `cleanup_failed`. Do not schedule a second move.

### Previous examples

- <https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8129>
- <https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8132>
- <https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23079> (stale object pool shard, INC-14689)

## Mass migration of repositories

This [balancer](https://gitlab.com/gitlab-com/gl-infra/balancer) project is meant to move gitaly repositories in bulk from one Gitaly node to another, in case of storage/disk saturation. The project is hosted on ops.gitlab.net and runs [scheduled job](https://ops.gitlab.net/gitlab-com/gl-infra/balancer/-/pipeline_schedules) to detect overloaded gitaly nodes and pick one (configurable) of them to move repositories away from it to a gitaly node with more available disk space. It currently moves around 1000 GB of project repositories on each run.

### Scheduled job

Currently [scheduled job](https://ops.gitlab.net/gitlab-com/gl-infra/balancer/-/pipeline_schedules) runs in production once a day at 01:00 UTC with following configurations (set via job variables):

- SHARD_LIMIT: 1 (Selects single shard to move repositories from)
- MOVE_AMOUNT: 1000 (Moves 1000 GB of projects or less)
- MOVE_LIMIT: -1 (There is no limit on the amount of repositories to move)

More information on CI variables is available here: <https://ops.gitlab.net/gitlab-com/gl-infra/balancer#using-balancer-through-ci>

### Project docs

For information related to project setup and running the job manually, please refer to project readme: <https://ops.gitlab.net/gitlab-com/gl-infra/balancer/-/blob/main/README.md>
Here is a recorded video of project walkthrough: <https://youtu.be/kEuYNVDpTUk>
