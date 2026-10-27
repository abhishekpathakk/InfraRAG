# Memorystore Redis TraceChunks Service

This is a [Memorystore for Redis](https://docs.cloud.google.com/memorystore/docs/redis/memorystore-for-redis-overview) instance managed by GCP.

## Connecting to Memorystore for Redis instance

Redis instance can be connected via redis-cli to run commands during debugging e.g. [`info` command](https://redis.io/docs/latest/commands/info/).

Production can be connected from a redis-cli in console servers e.g.

```shell
# Get AUTH_STRING from gcloud console
gcloud redis instances get-auth-string tracechunks-redis --region=us-east1 --project=gitlab-production

# SSH into console node
ssh console-01-sv-gprd.c.gitlab-production.internal

# Use AUTH_STRING obtained above to add REDISCLI_AUTH env
export REDISCLI_AUTH=<AUTH_STRING>

# Use redis-cli to connect to the instance with AUTH_STRING obtained above
/opt/gitlab/embedded/bin/redis-cli -h 10.239.0.4
```

Simlarly for staging:

```shell
# Get AUTH_STRING from gcloud console
gcloud redis instances get-auth-string tracechunks-redis --region=us-east1 --project=gitlab-staging-1

# SSH into console node
ssh console-01-sv-gstg.c.gitlab-staging-1.internal

# Use AUTH_STRING obtained above to add REDISCLI_AUTH env
export REDISCLI_AUTH=<AUTH_STRING>

# Use redis-cli to connect to the instance with AUTH_STRING obtained above
/opt/gitlab/embedded/bin/redis-cli -h 10.214.0.4
```
