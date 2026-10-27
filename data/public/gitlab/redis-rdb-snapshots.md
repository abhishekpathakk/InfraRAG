# Redis RDB Snapshots

We use RDB for [Redis
persistence](https://redis.io/docs/management/persistence/). In order to avoid a
performance hit on our primaries, we do **not** configure RDB snapshots via the
`save` configuration, but instead rely on the [gitlab-redis-backup
cookbook](https://gitlab.com/gitlab-cookbooks/gitlab-redis-backup/), which will
run a cron-like job to perform snapshots on all secondary nodes. If a given
primary has no healthy secondaries, the cookbook will allow it to perform
snapshots, so that at least one node has relatively up-to-date snapshots. See
[Avoid running Redis RDB backups on primary
nodes](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/566) for more
context.

## Troubleshooting

### Snapshots appear to not be running

#### Symptoms

- `redisRdbSaveDelayed` ("Last Redis RDB snapshot was X minutes ago") alerts

#### Actions

- Check the logs of the systemd timer with `sudo journalctl -u redis-rdb-backup`

## Restoring a snapshot

Redis will attempt to load a `dump.rdb` file on startup if it exists in the
server directory (`/var/opt/gitlab/redis` for our omnibus-gitlab managed
instances), so simply starting the redis process should suffice.
