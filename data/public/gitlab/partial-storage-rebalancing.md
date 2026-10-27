# Partial Gitaly Storage Rebalancing

To conserve space on Gitaly shards, we stop placing repositories in shards that
are over space-utilized above certain percentage (currently 80%). However, due
to organic growth in the existing repositories, disk utilization can still rise
up and potentially reach 100%.

To counteract this, we have a capacity warning
([example](https://gitlab.com/gitlab-com/gl-infra/capacity-planning-trackers/gitlab-com/-/work_items/2450))
that is triggered whenever the projected disk space utilization is going to
exceed a certain threshold. This document describes the actions needed to
resolve this alert by moving big repositories from heavily-utilized shards to
least-utilized ones.

## Procedure

1. Identify the heavily-utilized shards. Go to the ["gitaly service |
   disk_space
resource"](https://dashboards.gitlab.net/d/alerts-sat_disk_space/?var-environment=gprd&var-type=gitaly&var-stage=main&var-component=disk_space)
dashboard, sort the entries by "Last" descendingly. Any shard entry for the
`/dev/sdb` disk above the "aggregated disk_space" value is a candidate for
rebalancing. If there are no entries above, then the immediate values after
"aggregated disk_space" should be considered.
2. On each shard identified, we run the following:

    ```bash
    # ssh gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-uxyz.internal
    tmux
    sudo du -hcd 3 /var/opt/gitlab/git-data/repositories/@hashed | grep G | grep \\.git | tee /tmp/du
    ```

    The `du` command looks for repositories that are over 1 gigabyte, it will take some time to finish (usually within an hour) hence we run in it in a tmux session.
3. Once `du` finishes, we get the list of repositories we plan on moving out of the shard:

    ```bash
    sort -n /tmp/du | tail -n 50 | cut -d@ -f2 | cut -d. -f1 | sed -e 's/^/@/'
    ```

    Copy the output.
4. On the production Rails console, run the following script, replacing `<repos>` with the output we copied in the last step, and `<shard>` by the FQDN of the Gitaly shard we are processing:

    ```ruby
    # ssh console-01-sv-gprd.c.gitlab-production.internal
    # sudo gitlab-rails c
    hashes = '<repos>'
    projects = ProjectRepository.where(disk_path: hashes.split, shard: Shard.by_name('<shard>')).includes(:project).map(&:project).reject(&:forked?)
    projects.each { _1.repository_storage_moves.build(source_storage_name: _1.repository_storage).schedule }
    ```

    We exclude forks because moving them would also copy their object pool to
the new destination, and since we don't specify a destination (automatically
chosen by Rails to be a least-utilized shard), we risk potentially copying
object pools to different shards, increasing disk space, not reducing it.

    Projects that are the *source* of an object pool are not excluded by
`reject(&:forked?)`. Their move copies the pool first and fails with
`storage not found` if the pool row still names a decommissioned shard. Check
them before scheduling and handle any that fail the check with the
[stale object pool shard](./move-repositories.md#stale-object-pool-shard) steps:

    ```ruby
    projects.select(&:pool_repository).reject { _1.pool_repository.shard.name == _1.repository_storage }.map { [_1.id, _1.full_path, _1.pool_repository.shard.name] }
    ```

    The move service records the failure reason in `error_message` on the move
record. See [when the move fails](./move-repositories.md#when-the-move-fails)
for how to read it and which failures are safe to retry.
5. Note the projects we've moved in an internal note in the warning issue, for future bookkeeping.
6. Repeat for other identified shards.
7. Usually within a day the issue would be auto-closed, if not, then more shards needs rebalancing.
