# Scaling Redis Cluster

This document outlines the steps for scaling an existing Redis Cluster. Previous scaling Change Requests (CR) shows the operation in practice:

## Previous CRs for scaling `redis-cluster-ratelimiting`

- [Provision nodes for new shard in redis-cluster-ratelimiting](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18042)
- [Enable debug command](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18043) (If the cluster already doesn't have `debug` command enabled)
- [Migrate the keyslots](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18061)

## Setting up instances

This guide defines a few variables in `<>`, which are used in the scripts in this guide:

- `ENV`: `pre`, `gstg`, `gprd`
- `GCP_PROJECT`: `gitlab-production` or `gitlab-staging-1`
- `INSTANCE_TYPE`: `feature-flag`
- `SHARD_NUMBER`: sequential number of shard to be added e.g. in an existing cluster with 3 shards, this would be `04`

**Note:** To avoid mistakes in manually copy-pasting the variables in `<>` above during a provisioning session, it is recommended to prepare this doc with all the variables replaced beforehand.

Use them as environment variables in your local shell:

```
export ENV=<ENV>
export PROJECT=<GCP_PROJECT>
export DEPLOYMENT=redis-cluster-<INSTANCE_TYPE>
export SHARD_NUMBER=<SHARD_NUMBER>
```

### 1. Update Redis app user to deny execution of `debug` command

Redis clusters provisioned before April 2024, didn't have `debug` command enabled, so at first, we need to enable the `debug` command and add ACL for `rails` (or any other app user e.g. `registry`) user to deny `-debug` command for it.

Update `redis-cluster` gkms vault secrets to disable `debug` command for `rails` user, using these commands in the [`chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master):

```
./bin/gkms-vault-edit redis-cluster $ENV
```

Update the JSON payload to include `-debug` for `rails` user for the target Redis Cluster (There is a space between `-debug` and `<`):

```
    ...
    "rails on ~* &* +@all -debug ><RAILS_REDACTED>"
    ...
```

Complete json object, with modification:

```
{
  ...,
  "redis-cluster-<INSTANCE_TYPE>": {
    "redis_conf": {
      "masteruser": "replica",
      "masterauth": "<REPLICA_REDACTED>",
      "user": [
        "default off",
        "replica on ~* &* +@all ><REPLICA_REDACTED>",
        "console on ~* &* +@all ><CONSOLE_REDACTED>",
        "redis_exporter on +client +ping +info +config|get +cluster|info +slowlog +latency +memory +select +get +scan +xinfo +type +pfcount +strlen +llen +scard +zcard +hlen +xlen +eval allkeys ><EXPORTER_REDACTED>",
        "rails on ~* &* +@all -debug ><RAILS_REDACTED>"
      ]
    }
  }
}

```

This won't change anything yet, on the existing Redis servers, as we would reconfigure the Redis processes as mentioned later in this guide.

### 2. Create Chef role for new shard

Create chef role for the new Redis shard, based on the chef roles of existing Redis shards of the cluster. Also add `enable-debug-command` option to Redis configuration in the base role, if not added already.

An example MR can be found [here](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/4789).

### 3. Provision VMs

Provision the VMs for new Redis shard by incrementing `count` parameter to generic-stor/google terraform module of target Redis Cluster in the [config-mgmt project in the ops environment](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/). An example MR can be found [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/8474).

After the MR is merged and applied, check the VM state via:

```
gcloud compute instances list --project=$PROJECT | grep "$DEPLOYMENT-shard-$SHARD_NUMBER"
```

You need to wait for the initial chef-client run to complete.

One way to check is to tail the serial port output to check when the initial run is completed. An example:

```
gcloud compute --project=$PROJECT instances tail-serial-port-output $DEPLOYMENT-shard-$SHARD_NUMBER-01-db-$ENV --zone us-east1-{c/b/d}
```

Also ensure that instance was bootstrapped and configured successfully by checking if `startup-script` finished with exit status 0. If it is not zero then check the reason and fix it and restart the instance once to initialize journald properly.

```
gcloud compute --project=$PROJECT instances tail-serial-port-output $DEPLOYMENT-shard-$SHARD_NUMBER-01-db-$ENV --zone us-east1-{c/b/d} | grep 'startup-script exit status'
```

### 4. Add instances in new shard to the cluster

a. SSH into one of the previous instances:

```
ssh $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal
```

b. Run the following:

Note: here we are exporting these env vars in the shell within Redis server.

```
export ENV=<ENV>
export PROJECT=<GCP_PROJECT>
export DEPLOYMENT=redis-cluster-<INSTANCE_TYPE>
export SHARD_NUMBER=<SHARD_NUMBER>
```

c. Use the following command to connect the master-node to the cluster. Run this for per shard FQDN, where multiple shards are being added at once, like `$DEPLOYMENT-shard-<SHARD_NUMBER>-01-db-$ENV.c.$PROJECT.internal:6379`.

```
sudo gitlab-redis-cli --cluster add-node \
  $DEPLOYMENT-shard-$SHARD_NUMBER-01-db-$ENV.c.$PROJECT.internal:6379 \
  $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379

```

Use the following command to connect the remaining nodes to the cluster.  Update `{02,03,..m}` where `m` is the number of instances per shard.

```
for i in {02,03}; do
  master_node_id="$(sudo gitlab-redis-cli cluster nodes | grep $DEPLOYMENT-shard-$SHARD_NUMBER-01-db-$ENV.c.$PROJECT.internal | awk '{ print $1 }')";
  sudo gitlab-redis-cli --cluster add-node \
    $DEPLOYMENT-shard-$SHARD_NUMBER-$i-db-$ENV.c.$PROJECT.internal:6379 \
    $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379 \
    --cluster-slave --cluster-master-id master_node_id
    sleep 2
done
```

### 5. Validation

Check the status as following to verify that all expected master nodes are shown as FQDNs or IP addresses and `cluster_state` is `ok`, with all `16384` slots assigned:

```
$ sudo gitlab-redis-cli --cluster info $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379

redis-cluster-ratelimiting-shard-01-01-db-gprd.c.gitlab-production.internal:6379 (9b0828e3...) -> 78366 keys | 4096 slots | 2 slaves.
10.217.21.7:6379 (2c302ea5...) -> 78191 keys | 4097 slots | 2 slaves.
10.217.21.13:6379 (bce578ef...) -> 78822 keys | 4095 slots | 2 slaves.
10.217.21.2:6379 (17e6b401...) -> 78288 keys | 4096 slots | 2 slaves.
[OK] 313667 keys in 4 masters.
19.14 keys per slot on average.


$ sudo gitlab-redis-cli cluster info | head -n7
cluster_state:ok
cluster_slots_assigned:16384
cluster_slots_ok:16384
cluster_slots_pfail:0
cluster_slots_fail:0
cluster_known_nodes:12
cluster_size:4
```

## Enable `debug` command on Redis Cluster

As mentioned in the beginning, most of the existing Redis Clusters do not have `debug` command enabled, which is needed to fix the cluster state as part of troubleshooting broken cluster.

This step will enable the `debug` command by reconfiguring the existing Redis processes. Previous CR [here](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18043).

Run this from chef-repo, to find the existing Redis servers and reconfigure them via `redis-cluster-reconfigure.sh` in the runbooks repository, excluding new shard as it was configured already with `enable-debug-command` above during provisioning.

> [!warning]
> `enable-debug-command` config option must already be enabled for newly added nodes during the time of provisioning otherwise failover wouldn't work, which is required for reconfiguring the Redis process. Failover requires at least one keyslot to be present on the shard.

> [!caution]
> Before running `scripts/redis-cluster-reconfigure.sh`, check the content of `$DEPLOYMENT-nodes.txt` for any `knife` logs, remove such lines if any.

```
# cd chef-repo
knife search -i "roles:$ENV-base-db-$DEPLOYMENT" | sort -V | grep -v $SHARD_NUMBER > /tmp/$DEPLOYMENT-nodes.txt

# cd runbooks
scripts/redis-cluster-reconfigure.sh /tmp/$DEPLOYMENT-nodes.txt
```

## Scale out cluster by resharding Redis keys

The goal here is to distribute the number of keyslots among all shards equally (With some rounding off). By default, we have 16384 keyslots in a given Redis Cluster. Until now, we just added Redis instances for new shard to the cluster, but they do not have any Redis keys (keyslots) yet and hence they are not serving any user requests.

In this phase, we will migrate some keyslots from previous Redis shards to the new shard, so that new Redis instances start load sharing with existing Redis instances and hence lower their resource (CPU/Memory) utilization. Previous CR [here](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18061).

Check the current slot distribution:

```
glsh redis-cluster status --env $ENV --deployment $DEPLOYMENT
```

Dry run by default, `--apply` performs the reshard. The new shards are the masters with 0 slots, or pass `--shard 7,8`. Each existing master gives up its surplus over `16384 / <number of masters>`, one batch per source and destination pair:

```
glsh redis-cluster reshard --env $ENV --deployment $DEPLOYMENT --shard $SHARD_NUMBER
```

Apply it. The script prompts before each batch and runs `cluster info` and `--cluster check` after each one. It stops if the cluster is not healthy:

```
glsh redis-cluster reshard --env $ENV --deployment $DEPLOYMENT --shard $SHARD_NUMBER --apply
```

The default `--pipeline` of 100 is the `--cluster-pipeline` value: the number of keys read and written per `MIGRATE`. A larger value finishes faster but uses more CPU and memory on both masters and competes with user requests, especially for large `set`, `list`, or other multi-value keys. 100 was fine for [`redis-cluster-cache` in production](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22698), 30 for [`redis-cluster-ratelimiting`](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18061#note_1924076365). Watch CPU and memory saturation and Apdex on the Redis Cluster dashboard during each batch. Ctrl-C stops the current migration if it is hurting users. That usually leaves one slot half migrated, see troubleshooting below.

To move everything back off the new shard:

```
glsh redis-cluster rollback --env $ENV --deployment $DEPLOYMENT --shard $SHARD_NUMBER --apply
```

This only looks at the current distribution, so it also works after a partial migration.

### Validate application clients

Redis Cluster clients use `ASK` redirections while keyslots are migrating and `MOVED` redirections after ownership changes. Cluster-aware clients are expected to follow these redirections, retry commands, and update their routing without a process restart.

After every reshard batch, confirm the following application signals remain healthy before continuing:

- Check the [web service overview](https://dashboards.gitlab.net/d/web-main/web-overview?orgId=1) for the main and canary stages. Confirm the web error ratio and Apdex remain at their pre-reshard baselines.
- Check the [Sidekiq overview](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview?orgId=1) for increases in errors, retries, queue latency, queue depth, or saturation across all shards.
- Search the `pubsub-rails-inf-$ENV-*` index for new `NameError` exceptions from `lib/gitlab/markdown_cache/redis/extension.rb`.
- Load a repository commits page that contains rendered Markdown and confirm it succeeds through each webservice stage.
- Confirm `ASK` and `MOVED` redirections remain bounded and taper after the topology stabilizes.

Do not rely on Redis server health alone. For example, [INC-13206](https://app.incident.io/gitlab/incidents/13206) exposed a [client-side pipeline reply handling defect](https://github.com/redis-rb/redis-cluster-client/pull/547) while the Redis Cluster remained healthy.

### Troubleshooting

- If during migration, cluster configuration breaks for some reason (Redis process died or migration halted manually), then subsequent migrations will fail due to broken cluster state. Run the cluster fix command as follows, to recover from this situation:

```
ssh $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal
sudo gitlab-redis-cli --cluster fix 127.0.0.1:6379
```

- During migration, clients can receive `ASK` redirections to an importing node. After keyslot ownership changes, clients with an older route can receive `MOVED` redirections and update their keyslot mapping. These redirections are expected during online resharding and should taper after the topology stabilizes. Persistent or failed redirections, exhausted retries, or accompanying application errors require investigation.

#### Redirect-correlated application errors

If application errors increase during a reshard:

1. Stop starting new keyslot migrations.
2. Complete or repair the currently migrating keyslot and confirm that the Redis Cluster topology is healthy and stable.
3. Before restarting anything, preserve a sample exception, the affected pod name, the application image digest, and the redirection metrics.
4. If a restart is required to mitigate the errors, use the [Kubernetes rolling restart procedure](../kube/k8s-operations.md#rolling-restart) to replace only the affected client Deployments after the topology is stable.
5. Resume resharding only after Redis and application signals have recovered.

Preserve affected processes for investigation where possible rather than making a fleet restart part of the normal resharding procedure.

## Key metrics to observe

Below is a list of some of the key metrics to check for:

- Redis service error ratio e.g. [Dashboard link](https://dashboards.gitlab.net/d/redis-cluster-ratelimiting-main/redis-cluster-ratelimiting3a-overview?from=now-6h&orgId=1&to=now&var-PROMETHEUS_DS=PA258B30F88C30650&var-environment=gprd&var-shard=All&viewPanel=3422679610)
- Redis Cluster Slots Failed e.g. [Dashboard link](https://dashboards.gitlab.net/d/redis-cluster-ratelimiting-main/redis-cluster-ratelimiting3a-overview?orgId=1&var-PROMETHEUS_DS=PA258B30F88C30650&var-environment=gprd&var-shard=All&viewPanel=115&from=now-6h&to=now)
- Redirections for the clients e.g. [Dashboard link](https://dashboards.gitlab.net/d/redis-cluster-ratelimiting-main/redis-cluster-ratelimiting3a-overview?orgId=1&var-PROMETHEUS_DS=PA258B30F88C30650&var-environment=gprd&var-shard=All&viewPanel=117&from=now-6h&to=now)
- Webservice error ratio and Apdex for both main and canary e.g. [Dashboard link](https://dashboards.gitlab.net/d/web-main/web-overview?orgId=1)
- Sidekiq errors and retries across all shards e.g. [Dashboard link](https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview?orgId=1)
