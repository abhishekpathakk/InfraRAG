# Redis Cluster

## Core concepts

Redis Cluster is a mode of Redis to enable horizontal scaling. The dataset is divided among multiple nodes, allowing the computational load to be distributed.

How does Redis Cluster differ from non-clustered Sentinel-based Redis instances?

| Property | Sentinel | Cluster |
| --------- | ------ | ------ |
| Dataset | Every node has the entire dataset | Distributed over `n` nodes |
| Computation | Performed by master node | Performed by respective hash slot owner |
| Operations | All standard operations allowed | Cross-slot operations are not permitted |
| Scalability | Only vertical scaling | Increase cluster's shard size |
| Failovers | Coordinated by Sentinels | Coordinated by a quorum of master nodes |

References

- [Redis Cluster Specifications](https://redis.io/docs/reference/cluster-spec/)
- [Redis Cluster Scaling](https://redis.io/docs/management/scaling/)

## Glossary

**cluster**: A set of Redis nodes running in cluster-enabled mode.  In cluster mode, there are no Sentinel sidecar processes to perform monitoring, routing, and failover.  Instead, each Redis node communicates with all of its peers in a mesh, and clients are cluster-aware, connecting directly to these nodes.  In addition to the standard port that clients use, Redis nodes also use a "cluster bus" gossip protocol (on standard port + 10000) to exchange messages about cluster config updates, failure detection, failover authorization, etc. (see all gossip message types).

**shard**:In Redis Cluster, a shard is a discrete set of hash slots (defined below), owned by a group of Redis nodes (a master node and its replicas).  In some discussions we have alternately called this a "replica set", to distinguish it from our historical use of the term "shard" to represent client-managed "functional partitions" (where clients send certain keys to purpose-specific Redis targets such as `redis-sidekiq`, `redis-tracechunks`, etc.).

**node**: A single redis-server process, acting in either a master or replica role.  A Redis Cluster consists of a set of such nodes.  The cluster aims to have every hash slot owned by exactly 1 master (many-to-one), and each replica replicates the entirety of a single master (using the same async replication mechanism as with our current Sentinel-managed Redis nodes).  The cluster can dynamically reassign a node's role to compensate for node or connectivity failures, with the goal of ensuring that all hash slots are assigned to a healthy master node and all master nodes have a target number of replicas.

**hash slot**: The smallest unit of sharding. Every Redis Cluster has exactly 16384 hash slots.  Groups of hash slots are assigned as non-overlapping ranges to Redis master nodes (and their replicas).  Example:

```
Master[0] -> Slots 0 - 5460
Master[1] -> Slots 5461 - 10922
Master[2] -> Slots 10923 - 16383
```

Redis determines which shard stores a key by mapping that key to a hash slot using the [crc16 hash of the key or its hash](https://github.com/redis/redis/blob/7.0.7/src/cluster.c#L927-L952) tag and then checking which master node owns that hash slot.  The dictionary mapping hash slots to master nodes is locally cached by clients, and if a client's cached dictionary becomes out of date, Redis will redirect the client to the appropriate node, allowing the client to update its dictionary for future operations.

**cross-slot operations**: Multi-key commands containing keys which map to different hash slots. Any operations involving keys of different hash slot are deemed unsafe by Redis Cluster and rejected. For example, an `MGET` for keys of different hash slot is not possible to be served by a single master node since it may not own all the required hash slots.

**resharding**:  Migrating ownership of some hash slots from one shard to another.  This is a dynamic online operation, where Redis keys are migrated between nodes.  During a resharding operation, reads and writes to the keys being migrated are semantically safe but incur some extra overhead.  Also, multi-key requests may temporarily fail during the transitional state.  There are some documented corner cases where a failed resharding attempt must be manually completed.  In our environments, because we do not intend to dynamically add/remove nodes, resharding will be a rare and planned event (e.g. when adding new nodes to the cluster for additional capacity), not a frequent automated background activity.

replica migration - an optional feature that allows the cluster to dynamically reassign a replica from one master to another, to ensure all masters have at least N replicas.  This feature aims to improve availability.  However, it can counter-intuitively harm availability in either of 2 ways: it can lead to a master and its replicas being in the same availability zone ([details](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/1962#note_1140700451)), or it can lead to accumulating a majority of masters in the same availability zone ([details](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/1962#note_1140436657)).  This feature can be disabled ([cluster-allow-replica-migration](https://github.com/redis/redis/blob/7.0.7/redis.conf#L1662-L1668)) or tuned ([cluster-migration-barrier](https://github.com/redis/redis/blob/7.0.7/redis.conf#L1642-L1660)).  This is one of the topics to be addressed by scalability#2071.

## Observability

For most parts, the Grafana dashboard is the same as a Sentinel-based Redis dashboard. The difference lies in:

1. Cluster-specific panel: This panel tracks the slot coverage and state of nodes in the cluster. The components are defined in [`libsonnet/gitlab-dashboards/redis_common_graphs.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/ff4ff9dd29ee417a4a7d1940178c3085cc25730f/libsonnet/gitlab-dashboards/redis_common_graphs.libsonnet#L449).
2. `cluster_redirection` error SLI - tracks the rate of MOVED and ASK redirections. Redirections should only happen on (1) failover (requests are redirected to the new master), (2) resharding (requests are redirected to the new slot owner).

Cross-slot errors are prevented on the application side and should not reach the servers except for pipelined operations during resharding. The volume can be tracked on logs under 2 groups of fields:

1. `json.redis_<functional shard>_allowed_cross_slot_calls` shows the volume of [allowed](https://gitlab.com/gitlab-org/gitlab/-/blob/92312944bb8a827b5d00509a5d07d0fe8ee4955d/lib/gitlab/instrumentation/redis_cluster_validator.rb#L205) cross-slot calls (i.e. commands are accounted for and are running on non-cluster-based Redis)
2. `json.redis_<functional_shard>_cross_slot_calls` shows the volume of cross-slot commands (not accounted for or running on Redis Cluster)

## Troubleshooting

> **Not sure which Redis type you're on?** GitLab runs four distinct Redis deployment types and the tooling differs between them.
>
> - `redis-cluster-*` hostnames — VM Cluster (this page)
> - `redis-*` hostnames (no `cluster` in the name) — [VM Sentinel](redis.md)
> - Omnibus-managed nodes — [Omnibus Sentinel](redis.md) (no distinct hostname pattern; check for `gitlab-ctl` and `/opt/gitlab/embedded/bin/redis-cli`)
> - Kubernetes / pubsub workloads — [Kubernetes Redis](kubernetes.md)

### How to connect to the Redis CLI on a VM cluster node

> **Do not use bare `redis-cli` on VM cluster nodes.** It will connect but authentication will fail. Credentials on VM cluster nodes are managed via ACL entries in `/opt/redis/etc/redis.conf`, not via a simple `-a` password flag.

The [`gitlab-redis-cluster` cookbook](https://gitlab.com/gitlab-cookbooks/gitlab-redis-cluster) installs a wrapper script at `/opt/redis/gitlab-redis-cli`, also symlinked to `/usr/local/bin/gitlab-redis-cli`. The wrapper reads the `console` user's password directly from `/opt/redis/etc/redis.conf` and handles authentication for you.

```shell
# Verify connectivity
sudo gitlab-redis-cli ping
# Expected: PONG

# Confirm which ACL user you are authenticated as
sudo gitlab-redis-cli acl whoami
# Expected: "console"
```

If you need to connect as a different ACL user (e.g. the application user):

```shell
sudo gitlab-redis-cli --user rails acl whoami
```

**Key paths on every VM cluster node** (set by the [cookbook attributes](https://gitlab.com/gitlab-cookbooks/gitlab-redis-cluster/-/blob/master/attributes/default.rb)):

| Resource | Path |
| --- | --- |
| Redis binary | `/opt/redis/redis-server` |
| CLI wrapper | `/opt/redis/gitlab-redis-cli` (symlinked from `/usr/local/bin/gitlab-redis-cli`) |
| Redis config | `/opt/redis/etc/redis.conf` |
| Data / nodes file | `/var/opt/gitlab/redis/nodes.conf` |
| Log file | `/var/log/redis/redis.log` |

### What is the state of the cluster?

Start with `CLUSTER INFO` for a fast overview. If `cluster_state:ok` and `cluster_slots_ok:16384` are both present, the cluster is likely healthy.

```shell
sudo gitlab-redis-cli cluster info
```

Example output:

```
cluster_state:ok
cluster_slots_assigned:16384
cluster_slots_ok:16384
cluster_slots_pfail:0
cluster_slots_fail:0
cluster_known_nodes:9
cluster_size:3
```

Things to watch:

- `cluster_state` must be `ok` — anything else means at least one shard has no primary
- `cluster_slots_fail` must be `0` — non-zero means slots are currently unserved
- `cluster_slots_pfail` — non-zero means nodes are suspected down but not yet confirmed failed

For a full picture of every node's role and connection state, use `CLUSTER NODES`. Look for `fail` or `fail?` in the flags column (column 3):

```shell
sudo gitlab-redis-cli cluster nodes
```

Example output:

```
07c37dfeb235213a872192d90877d0cd55635b91 127.0.0.1:30004@31004,,shard-id=69bc080733d1355567173199cff4a6a039a2f024 slave e7d1eecce10fd6bb5eb35b9f99a514335d9ba9ca 0 1426238317239 4 connected
67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 127.0.0.1:30002@31002,,shard-id=114f6674a35b84949fe567f5dfd41415ee776261 master - 0 1426238316232 2 connected 5461-10922
292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 127.0.0.1:30003@31003,,shard-id=fdb36c73e72dd027bc19811b7c219ef6e55c550e master - 0 1426238318243 3 connected 10923-16383
6ec23923021cf3ffec47632106199cb7f496ce01 127.0.0.1:30005@31005,,shard-id=114f6674a35b84949fe567f5dfd41415ee776261 slave 67ed2db8d677e59ec4a4cefb06858cf2a1a89fa1 0 1426238316232 5 connected
824fe116063bc5fcf9f4ffd895bc17aee7731ac3 127.0.0.1:30006@31006,,shard-id=fdb36c73e72dd027bc19811b7c219ef6e55c550e slave 292f8b365bb7edb5e285caf0b7e6ddc7265d2f4f 0 1426238317741 6 connected
e7d1eecce10fd6bb5eb35b9f99a514335d9ba9ca 127.0.0.1:30001@31001,,shard-id=69bc080733d1355567173199cff4a6a039a2f024 myself,master - 0 0 1 connected 0-5460
```

To drill into the replicas of a specific master, use `CLUSTER REPLICAS <node-id>`. Run this on at least one node per shard to avoid a single-sided view:

```shell
sudo gitlab-redis-cli cluster replicas 97d7d00217fb53b9f4f74763f04be50c536dc470
```

For slot-level health, use `CLUSTER SLOTS` or `CLUSTER SHARDS`.

### How to check memory saturation

Memory saturation is a common alert on VM cluster nodes. Prefer the `Redis Data` row of the [service overview dashboard](https://dashboards.gitlab.net/d/redis-cluster-shared-state-main/redis-cluster-shared-state3a-overview?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&from=now-7d&to=now&timezone=utc&var-shard=$__all) over running commands on individual nodes. It has the `Memory Saturation`, `Memory Used`, `Redis RSS Usage` and `Memory Fragmentation` panels for every node in the cluster. The link is an example for `redis-cluster-shared-state`, for other clusters use the overview dashboard of that service.

To check memory utilization of redis via cli on a node, run the following:

```shell
sudo gitlab-redis-cli info memory
```

Key fields to check:

- `used_memory_human` — current memory in use
- `maxmemory_human` — the configured limit
- `mem_fragmentation_ratio` — values well above `1.5` indicate fragmentation; consider running [`MEMORY PURGE`](https://redis.io/commands/memory-purge/)
- `used_memory_rss_human` — RSS as seen by the OS, which includes fragmentation overhead

First check the eviction policy, as this determines how to interpret memory pressure:

```shell
sudo gitlab-redis-cli config get maxmemory-policy
```

If the policy is `noeviction` (which is the case for `redis-cluster-shared-state`), Redis will **not** evict keys when `maxmemory` is reached — instead, write commands will start failing with `OOM command not allowed`. In this case `evicted_keys` will stay at `0` even under full memory saturation, so it is not a reliable signal. Check `used_memory_human` against `maxmemory_human` directly.

If the policy is eviction-based (e.g. `allkeys-lru`), you can check whether keys are being dropped:

```shell
sudo gitlab-redis-cli info stats | grep evicted_keys
```

### How to check replication state

Prefer the `Replication` row of the [service overview dashboard](https://dashboards.gitlab.net/d/redis-cluster-shared-state-main/redis-cluster-shared-state3a-overview?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&from=now-7d&to=now&timezone=utc&var-shard=$__all) over running commands on individual nodes. It has the `Connected Secondaries`, `Replication Offset` and `Resync Events` panels. The link is an example for `redis-cluster-shared-state`, for other clusters use the overview dashboard of that service.

To check replication state via cli on a node, run the following:

```shell
sudo gitlab-redis-cli info replication
```

Key fields:

- `role` — should be `master` or `slave`
- `connected_slaves` — on primaries, should be greater than 0
- `master_link_status` — on replicas, should be `up`
- `master_sync_in_progress` — `1` means a full resync is underway, which can cause a temporary memory spike on the primary

If you suspect the replica output buffer limit is being hit (configured as `client-output-buffer-limit` in the role), check client list output:

```shell
sudo gitlab-redis-cli client list | grep replica
```

### How to check connected clients and slow queries

This information is already exposed via metrics and logs, so prefer these over running commands on individual nodes. The links below are examples for `redis-cluster-shared-state`.

- **Connected clients:** see the [Connected Clients panel](https://dashboards.gitlab.net/d/redis-cluster-shared-state-main/redis-cluster-shared-state3a-overview?orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&from=now-7d&to=now&timezone=utc&var-shard=$__all&viewPanel=panel-65) on the service overview dashboard. `maxclients` sets the maximum number of clients that can connect to a redis instance, and new connections are refused once `connected_clients` reaches it.
- **Slow queries:** see the [Redis slowlog in Kibana](https://log.gprd.gitlab.net/app/r/s/XntEo), which covers all nodes in the cluster. For other clusters, change the redis type filter to the cluster you are investigating. The `Slowlog Events` panels on the service overview dashboard show when slow commands occurred.

For other `redis-cluster-*` services, use the overview dashboard of that service.

### How to check the Redis service and logs

```shell
sudo systemctl status redis-server
sudo journalctl -u redis-server -n 100 --no-pager
sudo tail -100 /var/log/redis/redis.log
```

### How to initialize a new cluster

To initialize a cluster, see the [official Redis guide](https://redis.io/docs/management/scaling/#create-a-redis-cluster).

An example of how previous clusters were set up can be found in [here](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2210#note_1287069028).

### How to recover from all nodes going down

As the [gitlab-redis-cluster cookbook](https://gitlab.com/gitlab-cookbooks/gitlab-redis-cluster/-/blob/3dd0f008677d7e85121fe659428adcfc1277e904/attributes/default.rb#L14) defines a `cluster-config-file`, the nodes will attempt to recreate the original cluster topology using previously stored information from the file after a restart.

### How to force promotion of a replica in an emergency where Redis cannot heal itself

There is a sidecar process in each VM which checks the cluster health and forces a failover. See the [originating issue](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2140) for more information.

In the event where the sidecar processes are not working, the SRE/EOC will need to run the [`CLUSTER FAILOVER`](https://redis.io/commands/cluster-failover/) command on the desired slave node to promote that node into a master.

Run the following command on the desired node:

```
sudo gitlab-redis-cli CLUSTER FAILOVER TAKEOVER
```

### How to do online resharding (with warnings)?

See the [official Redis guide](https://redis.io/docs/management/scaling/#reshard-the-cluster).

### How do we rotate passwords in the ACL list?

TODO
