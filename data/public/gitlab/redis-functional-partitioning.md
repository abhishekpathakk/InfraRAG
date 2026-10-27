# Functional Partitioning

## Why partition?

Redis is a (mostly) single threaded application and thus can only use one CPU.  Some small amount of CPU can be offloaded to IO threads, but it is a small percentage.  This means that we have a hard upper limit for CPU capacity for any specific redis instance.  Partitioning allows us to get around this by splitting off part of the workload of an existing redis instance to a new, separate redis instance.  We are tracking this in [capacity planning issues](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/capacity-planning/), and should have a reasonable amount of warning if this needs to be done.

In the longer term, we're working on [redis cluster](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/823) to allow for horizontal scaling as well.

The other reason to partition redis would be for workload isolation, and that is a reason that will become the more common scenario after we have a functional horizontal scaling system.

## Timing

The last two redis partitions that we have done took between 3 - 6 weeks to complete.  The main factors that slow down or speed up the time required are the availability of reviewers for MRs, particularly for the application changes.  In general, tamland forecasts capacity out approximately three months, which should give us adequate time to partition if required.

## Determining what to split off

This is more of an art than a science, as it will require some amount of knowledge of the usage patterns of the redis in question.  We have documented how to [analyze memory usage](redis.md#redis-memory-analyzer) as well as [keyspace usage and network traffic](redis.md#keyspace-pattern-analysis), all of which can be combined to help determine what the largest chunk that makes logical sense to move is.

## Implementation

A lot of these processes are still a work in progress and will be modified based off of the results of [the epic to lessen sharding toil](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/886).

## Application changes

- Create a new redis store class. It should inherit from `Gitlab::Redis::Wrapper`. Configure its `config_fallback` to be the current store from which you're sharding off this workload.
- Add `use_primary_and_secondary_stores_for_<store_name>` and `use_primary_store_as_default_for_<store_name>` feature flags, matching the name of the new store.
- Update the relevant client code to use the new store.

[Example issue and MRs.](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2149)

## Infrastructure changes

With the [current k8s overhead due to the networking stack](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16871), we can only migrate workloads that are expected to remain well under saturation threshold to Kubernetes.  [See discussion points here.](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2130).  This means that in most cases, we'll likely be functionally sharding off onto VMs, but I've included the k8s documentation for when we can shift to using that more.  We presently do not have a well known method of creating a redis cluster shard, but that is work in progress as well.

### VMs

1. [Create a chef role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-db-redis-server-db-load-balancing.json)
2. [Provision in terraform](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/5009)
3. [Configure with redis-reconfigure.sh](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/redis-reconfigure.sh)

Step 1 and 2 will leave the cluster in a strange state, with each redis host believing they are the primary and a somewhat confused sentinel quorum.  In order to get things back in order, you'll need to run chef-client, gitlab-ctl reconfigure, and set each secondary to be a replica of the primary.  The redis-reconfigure.sh script does this for you.

```shell
./scripts/redis-reconfigure.sh $ENVIRONMENT $INSTANCE_NAME bootstrap
```

### K8s

1. [Create a new nodepool in terraform](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/4413)
2. [Update the deployment in ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/redis-pubsub)
3. Add secret to vault

### Redis-cluster

[Not yet implemented.](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/823))

## Observability

The new redis type will require a new set of dashboards created from the redis archetype.  [Example MR.](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/5386)

## Migration process

1. Create MRs to configure gitlab-rails for the new instance

This needs to be done in both chef and k8s.

Example MRs

[Chef](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/2892)
[K8s](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests/2558)

2. Update chef-repo vault with the correct key.

In the chef-repo repository, run the following command, and then update the section with the correct information.

```
$ bin/gkms-vault-edit gitlab-omnibus-secrets gprd

"gitlab-rails": {
...
  "redis_yml_override": {
    "db_load_balancing": {
      "url": "redis://<IAMAPASSWORD>@gprd-redis-db-load-balancing"
    }
  },
...
```

3. Use feature flags to turn on and off the dual writes

Use feature flags to transition to the new store. Between each step, check [error metrics](https://thanos.gitlab.net/graph?g0.expr=sum%20by%20(env%2C%20stage%2C%20instance_name)%20(rate(gitlab_redis_multi_store_pipelined_diff_error_total%5B1m%5D))&g0.tab=0&g0.stacked=0&g0.range_input=6h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D&g1.expr=rate(gitlab_redis_multi_store_method_missing_total%7Benv%3D%22gstg%22%7D%5B10m%5D)&g1.tab=1&g1.stacked=0&g1.range_input=6h&g1.max_source_resolution=0s&g1.deduplicate=1&g1.partial_response=0&g1.store_matches=%5B%5D) and [error logs](https://nonprod-log.gitlab.net/goto/781e9c40-ad59-11ed-9af2-6131f0ee4ce6).

You should also let enough time elapse between feature toggles to "warm up" the new store.  The amount of time required to warm up a new instance depends on the usage pattern.  Often, looking at the info keyspace ttl (which is in milliseconds) and multiplying it times two will get you a pretty good guestimate.  For some usage patterns, we do not have a TTL set, and those will require a different method of rollout.  See [scalability #2193](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2193) for more information.

The sequence of feature flag toggles you want to follow is:

- Turn on `use_primary_and_secondary_stores_for_<store_name>`

- Turn on `use_primary_store_as_default_for_<store_name>`

- Turn off `use_primary_and_secondary_stores_for_<store_name>`

After the first feature flag is toggled, you should begin to see activity on your new instance.  Look for overall RPS, primary RPS and connected clients on the appropriate Grafana dashboard.  Another good command to use is info keyspace on the new redis instance.

Before dual writes:

```
sudo gitlab-redis-cli
0.0.0.0:6379> info keyspace
# Keyspace
0.0.0.0:6379>
```

After dual writes:

```
0.0.0.0:6379> info keyspace
# Keyspace
db0:keys=8319,expires=8319,avg_ttl=14836
```

[Example change request](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8393)

Double check the appropriate feature flags as there has been a lot of [discussion around how MultiStore works](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2161).

## Verification

Dashboards for both the new and old redis stores will provide some good insights into the before and after usage.

[This thanos query](https://thanos.gitlab.net/graph?g0.expr=label_replace(avg_over_time(gitlab_component_saturation%3Aratio%7Benv%3D%22gprd%22%2Cenvironment%3D%22gprd%22%2Ctype%3D%22redis%22%2Ccomponent%3D%22redis_primary_cpu%22%7D%5B1m%5D)%2C%20%27time%27%2C%20%27now%27%2C%20%27%27%2C%20%27%27)%0Aor%0Alabel_replace(avg_over_time(gitlab_component_saturation%3Aratio%7Benv%3D%22gprd%22%2Cenvironment%3D%22gprd%22%2Ctype%3D%22redis%22%2Ccomponent%3D%22redis_primary_cpu%22%7D%5B1m%5D%20offset%201w)%2C%20%22time%22%2C%20%27offset-1w%27%2C%20%27%27%2C%20%27%27)&g0.tab=0&g0.stacked=0&g0.range_input=1h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D) which compares week over week primary_cpu usage is also a good one to use.
