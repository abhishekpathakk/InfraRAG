# Recovering from CI Patroni cluster lagging too much or becoming completely broken

**IMPORTANT:** This troubleshooting only applies before CI decomposition is finished (ie. `patroni-ci` is still just a standby replica of `patroni`), after `patroni-ci` is promoted as Writer this runbook is no longer valid.

## Symptoms

We have several alerts that detect replication problems, but this Runbook should only be considered if these alerts are related with the `Standby Leader` of our `patroni-ci` cluster, otherwise please consider this incident as a [regular Replica lagging issue](https://gitlab.com/gitlab-com/runbooks/-/blob/202ea907ce949198cec1b0f901f11a8bfb3acadd/docs/patroni/postgres.md#replication-is-lagging-or-has-stopped);

Possible related alerts are:

- Alert that replication is stopped
- Alert that replication lag is over 2min (over 120m on archive and delayed
replica)
- Alert that replication lag is over 200MB

To check what node is the `Standby Leader` of our `patroni-ci` cluster execute `ssh patroni-ci-01-db-gprd.c.gitlab-production.internal "sudo gitlab-patronictl list"`

## Possible checks

- Check for lag pile up (continuous lag increase without reducing) in the `patroni-ci` Standby Leader [lag in Thanos](https://thanos.gitlab.net/graph?g0.expr=pg_replication_lag%7Benv%3D%22gprd%22%2C%20type%3D%22patroni-ci%22%7D&g0.tab=0&g0.stacked=0&g0.range_input=2d&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)
- Check if the CI Standby Leader can't find WAL segments from WAL stream
   1. SSH into the Standby Leader of `patroni-ci` cluster
   2. Check the `/var/log/gitlab/postgresql/postgresql.csv` log file for errors like `FATAL,XX000,"could not receive data from WAL stream: ERROR: requested WAL segment ???????????? has already been removed"`
- [Search `patroni-ci` logs into Elastic](https://log.gprd.gitlab.net/goto/54b89750-da38-11ec-aade-19e9974a7229) for `FATAL` error and messages like `XX000` or `"could not receive data from WAL stream"`

## Resolution

This procedure can recover from `patroni-ci` being broken but was designed as a
[rollback procedure in case CI decomposition failover fails](https://gitlab.com/gitlab-org/gitlab/-/issues/361759).

This solution will not be applicable once CI decomposition is finished
and the CI cluster is diverged fully from Main.

Before we've finished CI decomposition the Patroni CI cluster is just another
set of replicas and is only used for `read-only` traffic by `gitlab-rails`.
This means it is quite simple to recover if the cluster becomes corrupted, too
lagged behind or otherwise unavailable. The solution is to just send all CI
`read-only` traffic to Main Patroni replicas. The quickest way to do this is
reconfigure all Patroni Main replicas to also present as
`ci-db-replica.service.consul`.

The resolution to this problem basically consist into temporarily routing the CI `read-only` workload from the `patroni-ci`
cluster in our `patroni-main` Replicas, while we can rebuild and re-sync the `patroni-ci` cluster.

To handle the CI `read-only` workload in case of incident, all `patroni-main` nodes have 3 additional pgbouncers deployed and listening in 6435, 6436 and 6437 TCP ports.
If they are not being used these ports are defined as `idle-ci-db-replica` Consul service name and as the name suggests, nothing points at these extra pgbouncers.

### Resolution Steps - Route CI read-only workload to Main

In case of incident you will have to:

- **1.** In `patroni-main` nodes, rename the Consul service `idle-ci-db-replica` to `ci-db-replica`. We have a [sample MR at for what this would involve](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/1952/diffs)
- **2.** In `patroni-ci` nodes, rename Consul service name from `ci-db-replica` to `dormant-ci-db-replica`. We have a [sample MR at for what this would involve](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/1875/diffs)

_Note: In case these MRs are unavailable the diffs are:_

<details><summary>Diff for reconfiguring Patroni cluster to also present as ci-db-replica in Consul</summary>

```diff
diff --git a/roles/gprd-base-db-patroni-v12.json b/roles/gprd-base-db-patroni-v12.json
--- a/roles/gprd-base-db-patroni-v12.json
+++ b/roles/gprd-base-db-patroni-v12.json
@@ -5,9 +5,9 @@
    "gitlab-pgbouncer": {
      "consul": {
        "port_service_name_overrides": {
-          "6435": "idle-ci-db-replica",
-          "6436": "idle-ci-db-replica",
-          "6437": "idle-ci-db-replica"
+          "6435": "ci-db-replica",
+          "6436": "ci-db-replica",
+          "6437": "ci-db-replica"
        }
      },
      "listen_ports": [

diff --git a/roles/gprd-base-db-patroni-ci.json b/roles/gprd-base-db-patroni-ci.json
--- a/roles/gprd-base-db-patroni-ci.json
+++ b/roles/gprd-base-db-patroni-ci.json
@@ -5,7 +5,7 @@
  "default_attributes": {
    "gitlab-pgbouncer": {
      "consul": {
-        "service_name": "ci-db-replica"
+        "service_name": "dormant-ci-db-replica"
      },
      "databases": {
        "gitlabhq_production": {
```

</details>

- **3.** You will likely want to apply this as quickly as possible by running chef
directly on all the Patroni Main nodes.

- **4.** Once you've done this you will have to
do 1 minor cleanup on Patroni CI nodes, since the `gitlab-pgbouncer` cookbook
does not handle renaming `service_name` you will also need to delete
`/etc/consul/conf.d/ci-db-replica*.json` from the problematic CI Patroni nodes, by executing:
   1. `knife ssh -C 10 'roles:gprd-base-db-patroni-ci' 'sudo rm -f /etc/consul/conf.d/ci-db-replica*.json'`
   1. `knife ssh -C 10 'roles:gprd-base-db-patroni-ci' 'sudo consul reload'`

- **5.** Validate Consul resolver should return just `patroni-v12` (aka `patroni-main`) replica hosts, by running `dig @localhost ci-db-replica.service.consul +short SRV | sort -k 4`, like for example:

   <details><summary>Name resolution for `ci-db-replica.service.consul` after route of CI read-only workload to Main is done</summary>

   ```dig
   $ dig @localhost ci-db-replica.service.consul +short SRV | sort -k 4
   1 1 6435 patroni-v12-01-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-01-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-01-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-02-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-02-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-02-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-03-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-03-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-03-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-04-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-04-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-04-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-06-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-06-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-06-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-07-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-07-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-07-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-08-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-08-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-08-db-gprd.node.east-us-2.consul.
   1 1 6435 patroni-v12-09-db-gprd.node.east-us-2.consul.
   1 1 6436 patroni-v12-09-db-gprd.node.east-us-2.consul.
   1 1 6437 patroni-v12-09-db-gprd.node.east-us-2.consul.
   ```

   </details>

- **6.** Verify that CI read requests are shifting:

  - From [CI Read requests in patroni-ci](https://thanos.gitlab.net/graph?g0.expr=(sum(rate(pg_stat_user_tables_idx_tup_fetch%7Benv%3D%22gprd%22%2C%20relname%3D~%22(ci_.*%7Cexternal_pull_requests%7Ctaggings%7Ctags)%22%2Cinstance%3D~%22patroni-ci-.*%22%7D%5B1m%5D))%20by%20(relname%2C%20instance)%20%3E%201)%20and%20on(instance)%20pg_replication_is_replica%3D%3D1&g0.tab=0&g0.stacked=0&g0.range_input=6h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)
  - To [CI Read requests in patroni-main](https://thanos.gitlab.net/graph?g0.expr=(sum(rate(pg_stat_user_tables_idx_tup_fetch%7Benv%3D%22gprd%22%2C%20relname%3D~%22(ci_.*%7Cexternal_pull_requests%7Ctaggings%7Ctags)%22%2Cinstance%3D~%22patroni-v12-.*%22%7D%5B1m%5D))%20by%20(relname%2C%20instance)%20%3E%201)%20and%20on(instance)%20pg_replication_is_replica%3D%3D1&g0.tab=0&g0.stacked=0&g0.range_input=6h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)

### Resolution Steps - Redeploy and Resync the Patroni CI cluster

Fistly, escalate the incident to a DBRE and ask them to proceed with the recovery of the broken CI Patroni cluster using a Snapshot from the Master cluster (instead of pg_basebackup).

Once the CI Patroni cluster has fully recovered you can revert these
changes but you should do this in 2 MRs using the following steps:

- **1.** Change `roles/gstg-base-db-patroni-ci.json`
   back to `service_name: ci-db-replica` . Then wait for chef to run on
   CI Patroni nodes and confirm they are correctly registering in consul
   under DNS `ci-db-replica.service.consul`

  - You can validate by running `dig @localhost ci-db-replica.service.consul +short SRV | sort -k 4` and the resolver should return both `patroni-v12` (aka `patroni-main`) and `patroni-ci` replica hosts, like for example:
      <details><summary>Name resolution for `ci-db-replica.service.consul` SRV name </summary>

      ```dig
      $ dig @localhost ci-db-replica.service.consul +short SRV | sort -k 4
      1 1 6432 patroni-ci-02-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-02-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-02-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-04-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-04-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-04-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-05-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-05-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-05-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-06-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-06-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-06-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-07-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-07-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-07-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-08-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-08-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-08-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-09-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-09-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-09-db-gprd.node.east-us-2.consul.
      1 1 6432 patroni-ci-10-db-gprd.node.east-us-2.consul.
      1 1 6433 patroni-ci-10-db-gprd.node.east-us-2.consul.
      1 1 6434 patroni-ci-10-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-01-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-01-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-01-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-02-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-02-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-02-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-03-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-03-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-03-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-04-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-04-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-04-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-06-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-06-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-06-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-07-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-07-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-07-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-08-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-08-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-08-db-gprd.node.east-us-2.consul.
      1 1 6435 patroni-v12-09-db-gprd.node.east-us-2.consul.
      1 1 6436 patroni-v12-09-db-gprd.node.east-us-2.consul.
      1 1 6437 patroni-v12-09-db-gprd.node.east-us-2.consul.
      ```

      </details>

- **2.** Revert the `port_service_name_overrides` in `roles/gprd-base-db-patroni-main.json` to `idle-ci-db-replica` so that `patroni-main` nodes stop registering in Consul for `ci-db-replica.service.consul`

- **3.** Remove `/etc/consul/conf.d/dormant-ci-db-replica*.json` from CI Patroni nodes as this is no longer needed and Chef won't clean this up for you
   1. `knife ssh -C 10 'roles:gprd-base-db-patroni-ci' 'sudo rm -f /etc/consul/conf.d/dormant-ci-db-replica*.json'`
   1. `knife ssh -C 10 'roles:gprd-base-db-patroni-ci' 'sudo consul reload'`

- **4.** Verify the that DNS resolve for `ci-db-replica.service.consul` is only returning `patroni-ci` nodes,
   by executing `dig @localhost ci-db-replica.service.consul +short SRV | sort -k 4`

- **5.**  Verify that CI read requests shifted back:
  - From [CI Read requests in patroni-main](https://thanos.gitlab.net/graph?g0.expr=(sum(rate(pg_stat_user_tables_idx_tup_fetch%7Benv%3D%22gprd%22%2C%20relname%3D~%22(ci_.*%7Cexternal_pull_requests%7Ctaggings%7Ctags)%22%2Cinstance%3D~%22patroni-v12-.*%22%7D%5B1m%5D))%20by%20(relname%2C%20instance)%20%3E%201)%20and%20on(instance)%20pg_replication_is_replica%3D%3D1&g0.tab=0&g0.stacked=0&g0.range_input=6h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)
  - To [CI Read requests in patroni-ci](https://thanos.gitlab.net/graph?g0.expr=(sum(rate(pg_stat_user_tables_idx_tup_fetch%7Benv%3D%22gprd%22%2C%20relname%3D~%22(ci_.*%7Cexternal_pull_requests%7Ctaggings%7Ctags)%22%2Cinstance%3D~%22patroni-ci-.*%22%7D%5B1m%5D))%20by%20(relname%2C%20instance)%20%3E%201)%20and%20on(instance)%20pg_replication_is_replica%3D%3D1&g0.tab=0&g0.stacked=0&g0.range_input=6h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)
