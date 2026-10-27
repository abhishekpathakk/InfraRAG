# Interacting with Consul

## CLI

The `consul` CLI is very extensive.  Check out [Consul's Commands Documentation](https://developer.hashicorp.com/consul/commands)

## Useful Commands

To [identify the current server](https://developer.hashicorp.com/consul/commands/operator/raft) with the leader role:

```shell
$ consul operator raft list-peers
Node                       ID                                    Address             State     Voter  RaftProtocol
consul-gl-consul-server-3  c929bb0e-0263-c870-4b7e-1ea7a25a39a2  10.227.16.79:8300   leader    true   3
consul-gl-consul-server-2  e607642d-a79c-838a-31bd-da25a2c77bfd  10.227.11.13:8300   follower  true   3
consul-gl-consul-server-1  5d947b27-ef5f-f3c6-17b1-bd93b19e3fc0  10.227.22.175:8300  follower  true   3
consul-gl-consul-server-0  5342d066-32b5-29cb-7c10-51aa5c89e23c  10.227.2.236:8300   follower  true   3
consul-gl-consul-server-4  2e3075d9-f13f-429d-0010-d2190a40bc31  10.227.5.16:8300    follower  true   3
```

To [follow the debug logs](https://developer.hashicorp.com/consul/commands/monitor) of a Consul agent:

```shell
consul monitor -log-level debug
```

### Get the full key/value tree as JSON

```shell
consul kv export | jq .
```

### Some interesting commands for Patroni

* get the Patroni leader

  ```shell
  consul kv get service/gstg-pg12-patroni-registry/leader
  ```

* get the Patroni attributes of a Patroni node

  ```shell
  consul kv get service/pg12-ha-cluster-stg/members/patroni-06-db-gstg.c.gitlab-staging-1.internal
  ```

* The DNS name of the primary database: `master.patroni.service.consul`
* The round-robin DNS name of the replicas: `replica.patroni.service.consul`

More to be found [here](../pgbouncer/patroni-consul-postgres-pgbouncer-interactions.md).

## External Queries

Our primary use of Consul is for service discovery.  If you know the name of the
service you intend on querying, you can perform a lookup to the agent locally:

```shell
dig @127.0.0.1 -p 8600 <service_name>
```

## Web UI and local Consul CMD

We enable the web UI, but do not easily expose it.  Follow the instructions
below to access the full catalog of consul using their UI:

1. Connect to the GKE cluster where Consul is hosted:

   ```shell
   glsh kube use-cluster gprd
   ```

2. On a separate terminal, forward the Consul Server service port:

   ```shell
   kubectl port-forward service/consul-gl-consul-expose-servers 8500:8500 -n consul
   ```

3. Open a browser and point it to <http://localhost:8500>
4. You can also use the `consul` command on a terminal. Eg:

   ```shell
   consul members
   ```

5. Enjoy
