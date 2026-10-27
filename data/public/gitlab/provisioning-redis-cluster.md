# Provisioning Redis Cluster

This document outlines the steps for provisioning a Redis Cluster. Former attempts are documented here:

- [`redis-cluster-ratelimiting`](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2256)
- [`redis-cluster-chat-cache`](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2358)

## Setting up instances

First, this guide defines a few variables in `<>`, namely:

- `ENV`: `pre`, `gstg`, `gprd`
- `GCP_PROJECT`: `gitlab-production` or `gitlab-staging-1`
- `INSTANCE_TYPE`: `feature-flag`
- `RAILS_INSTANCE_NAME`: The name that GitLab Rails would recognise. This matches `redis.xxx.yml` or the 2nd-top-level key in `redis.yml` (top-level key being `production`)
- `RAILS_INSTANCE_NAME_OMNIBUS`: `RAILS_INSTANCE_NAME` but using underscore, i.e. `feature_flag` instead of `feature-flag`
- `RAILS_CLASS_NAME`: The class which would connect to the new Redis Cluster. e.g. `Gitlab::Redis::FeatureFlag`.
- `REPLICA_REDACTED`: Generated in [Generate Redis passwords step](#1-generate-redis-passwords)
- `RAILS_REDACTED`: Generated in [Generate Redis passwords step](#1-generate-redis-passwords)
- `EXPORTER_REDACTED`: Generated in [Generate Redis passwords step](#1-generate-redis-passwords)
- `CONSOLE_REDACTED`: Generated in [Generate Redis passwords step](#1-generate-redis-passwords)

When configuring the application, note that the name of the instance must match the object name in lowercase and kebab-case/snake-case in the application.
E.g. We have `redis-cluster-chat-cache` service but in GitLab Rails, the object is `Gitlab::Redis::Chat`. Hence `chat` should be used when configuring the secret for the application in console and Kubernetes.

**Note:** To avoid mistakes in manually copy-pasting the variables in `<>` above during a provisioning session, it is recommended to prepare this doc with all the variables replaced beforehand.

### 1. Generate Redis passwords

Generate four passwords, `REPLICA_REDACTED`, `RAILS_REDACTED`, `EXPORTER_REDACTED`, and `CONSOLE_REDACTED` using:

```
for I in REPLICA_REDACTED RAILS_REDACTED EXPORTER_REDACTED CONSOLE_REDACTED; do echo $I; openssl rand -hex 32; done
```

Update both `redis-cluster` and `redis-exporter` gkms vault secrets using these commands in the [`chef-repo`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master):

```
./bin/gkms-vault-edit redis-cluster <ENV>
```

Update the JSON payload to include the new instance details:

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

Do the same for

```
./bin/gkms-vault-edit redis-exporter <ENV>
```

Modify the existing JSON

```
{
  "redis_exporter": {
    "redis-cluster-<INSTANCE_TYPE>": {
      "env": {
        "REDIS_PASSWORD": "<EXPORTER_REDACTED>"
      }
    }
  }
}

```

### 2. Create Chef roles

Set the new chef roles and add the new role to the list of gitlab-redis roles in <ENV>-infra-prometheus-server role.

An example MR can be found [here](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/3494).

### 3. Provision VMs

Provision the VMs via the generic-stor/google terraform module. This is done in the [config-mgmt project in the ops environment](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/). An example MR can be found [here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/5811).

After the MR is merged and applied, check the VM state via:

```
gcloud compute instances list --project <GCP_PROJECT> | grep 'redis-cluster-<INSTANCE_TYPE>'
```

You need to wait for the initial chef-client run to complete.

One way to check is to tail the serial port output to check when the initial run is completed. An example:

```
gcloud compute --project=<GCP_PROJECT> instances tail-serial-port-output redis-cluster-<INSTANCE_TYPE>-shard-01-01-db-<ENV> --zone us-east1-{c/b/d}

```

### 4. Initialising the cluster

a. SSH into one of the instance:

```
ssh redis-cluster-<INSTANCE_TYPE>-shard-01-01-db-<ENV>.c.<GCP_PROJECT>.internal
```

b. Run the following:

```
export ENV=<ENV>
export PROJECT=<GCP_PROJECT>
export DEPLOYMENT=redis-cluster-<INSTANCE_TYPE>
```

c. Use the following command to connect the master-nodes and initialise a working cluster. Add more shard FQDN where necessary. e.g. `$DEPLOYMENT-shard-<shard_number>-01-db-$ENV.c.$PROJECT.internal:6379`.

```
sudo gitlab-redis-cli --cluster create \
  $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379 \
  $DEPLOYMENT-shard-02-01-db-$ENV.c.$PROJECT.internal:6379 \
  $DEPLOYMENT-shard-03-01-db-$ENV.c.$PROJECT.internal:6379

```

Use the following command to connect the remaining nodes to the cluster.  Update `{01, 02, 03, ... n}-{02,03,..m}` where `n` is the number of shards and `m` is the number of instances per shard.

```

for i in {01,02,03}-{02,03}; do
  sudo gitlab-redis-cli --cluster add-node \
    $DEPLOYMENT-shard-$i-db-$ENV.c.$PROJECT.internal:6379 \
    $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379
  sleep 2
done
```

Use the following command, to assign the replicas within each shard. Update `{01, 02, 03, ... n}-{02,03,..n}` where necessary depending on the cluster-size.

```
for i in {01,02,03}; do
  for j in {02,03}; do
    node_id="$(sudo gitlab-redis-cli cluster nodes | grep $DEPLOYMENT-shard-$i-01-db-$ENV.c.$PROJECT.internal | awk '{ print $1 }')";
    sudo gitlab-redis-cli -h $DEPLOYMENT-shard-$i-$j-db-$ENV.c.$PROJECT.internal \
      cluster replicate $node_id
  done
done
```

### 5. Validation

Wait for a few seconds as the nodes need time to gossip. Check the status via:

```
$ sudo gitlab-redis-cli --cluster info $DEPLOYMENT-shard-01-01-db-$ENV.c.$PROJECT.internal:6379

redis-cluster-ratelimiting-shard-01-01-db-gprd.c.gitlab-production.internal:6379 (9b0828e3...) -> 0 keys | 5461 slots | 2 slaves.
10.217.21.3:6379 (ac03fcee...) -> 0 keys | 5461 slots | 2 slaves.
10.217.21.4:6379 (f8341afd...) -> 0 keys | 5462 slots | 2 slaves.
[OK] 0 keys in 3 masters.
0.00 keys per slot on average.


$ sudo gitlab-redis-cli cluster info | head -n7
cluster_state:ok
cluster_slots_assigned:16384
cluster_slots_ok:16384
cluster_slots_pfail:0
cluster_slots_fail:0
cluster_known_nodes:9
cluster_size:3
```

## Configuring the applications

### 1. Configure console instances

a. Proxy and authenticate to Hashicorp Vault:

```
glsh vault proxy

export VAULT_PROXY_ADDR="socks5://localhost:18200"
glsh vault login
```

```
vault kv get -format=json chef/env/<ENV>/shared/gitlab-omnibus-secrets | jq '.data.data' > data.json
cat data.json | jq --arg PASSWORD <RAILS_REDACTED> '."omnibus-gitlab".gitlab_rb."gitlab-rails".redis_yml_override.<RAILS_INSTANCE_NAME_OMNIBUS>.password = $PASSWORD' > data.json.tmp
diff -u data.json data.json.tmp
mv data.json.tmp data.json
vault kv patch chef/env/<ENV>/shared/gitlab-omnibus-secrets @data.json
rm data.json

OR

glsh vault edit-secret chef env/<ENV>/shared/gitlab-omnibus-secrets
#  Add the following object in ."omnibus-gitlab".gitlab_rb."gitlab-rails".redis_yml_override :
#  "<RAILS_INSTANCE_NAME_OMNIBUS>": {
#    "password": <RAILS_REDACTED>
#  }
```

Update roles/<ENV>-base.json with the relevant connection details. An example MR can be found [here](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/3546).

### 2. Verification of config in a VM

Check the confirmation detail by using `gitlab-rails console` inside a console instance. You may need to run `chef-client` to update the node and render the updated configuration files. This is important as the pipeline does not check the correctness of the config files. This may impact the deploy-node as GitLab Rails connects to Redis instances on start-up. There was a past incident of such an [issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/16322) for reference.

```
[ gstg ] production> Gitlab::Redis::FeatureFlag.with{|c| c.ping} # replace Gitlab::Redis::FeatureFlag with <RAILS_CLASS_NAME>
=> "PONG"
[ gstg ] production>
```

### 3. Configure Gitlab Rails

a. Update secret

```
vault kv put k8s/env/<ENV>/ns/gitlab/redis-cluster-<INSTANCE_TYPE>-rails password=<RAILS_REDACTED>
```

For example,

```
vault kv get k8s/env/<ENV>/ns/gitlab/redis-cluster-<INSTANCE_TYPE>-rails

======================== Secret Path ========================
k8s/data/env/gprd/ns/gitlab/redis-cluster-ratelimiting-rails

======= Metadata =======
Key                Value
---                -----
created_time       2023-03-18T00:33:29.790293426Z
custom_metadata    <nil>
deletion_time      n/a
destroyed          false
version            1

====== Data ======
Key         Value
---         -----
password    <RAILS_REDACTED>

```

Note the version of the password in `vault kv get` and make sure it tallies with the external secret definition in [k8s-workload](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab-external-secrets/values/values.yaml.gotmpl):

```
gitlab-redis-cluster-<INSTANCE_TYPE>-rails-credential-v1:
  refreshInterval: 0
  secretStoreName: gitlab-secrets
  target:
    creationPolicy: Owner
    deletionPolicy: Delete
  data:
    - remoteRef:
        key: env/{{ $env }}/ns/gitlab/redis-cluster-<INSTANCE_TYPE>-rails
        property: password
        version: "1"
      secretKey: password
```

Note that when rotating secrets (eg having v1 in `gstg` and v2 in `gprd`), follow a safe and controlled rollout as described [here](../vault/usage.md#rotating-kubernetes-secrets).

b. Update Gitlab Rails `.Values.global.redis` accordingly.

Either add a new key to `.Values.global.redis.<RAILS_INSTANCE_NAME>` or `.Values.global.redis.redisYmlOverride.<RAILS_INSTANCE_NAME>`. An example MR can be found [here](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests/2753).

### 4. Troubleshooting

#### No metrics on dashboard

This was encountered when provisioning the [production instance of redis-cluster-chat-cache](https://gitlab.com/gitlab-com/gl-infra/observability/team/-/issues/2358#note_1406105979). To resolve this, run chef-repo on Prometheus with:

```
knife ssh roles:gprd-infra-prometheus-server "sudo chef-client"
```
