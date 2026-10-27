# PatroniLeadershipAlertsNoData

## Overview

One of the inputs to [PatroniNoHealthyPrimary](PatroniNoHealthyPrimary.md) or
[PatroniNoReplicaStreaming](PatroniNoReplicaStreaming.md) has been missing for 10 minutes. Until
it's back, the paging alert that depends on it **can't fire** for this cluster. This alert doesn't
mean the database is unhealthy.

| Missing series | Comes from | Paging alert it blinds |
| --- | --- | --- |
| `consul_catalog_service_node_healthy{service_id="<type>-master"}` | `consul_exporter`, querying the Consul servers | PatroniNoHealthyPrimary |
| `pg_replication_is_replica{type="<type>", shard="default"}` | `postgres_exporter` on each Patroni node | PatroniNoReplicaStreaming |

## Common causes

- **The consul_exporter pod is down.** It currently runs as a single pod, so every Patroni cluster
  fires at once. Check the pod and its scrape target.
- **The cluster was renamed.** A major-version cutover can change the Consul service name or the
  `type` label, which comes from the VM's GCE labels in config-mgmt (for example `patroni-ci-v18`).
  Both selectors are built from the cluster's metrics-catalog `type` in `consulSelector` and `postgresSelector`
  ([`libsonnet/alerts/patroni-leadership-alerts.libsonnet`](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-leadership-alerts.libsonnet)).
  Restore the original names on the cluster, or update those selectors to match.
- **postgres_exporter is down on every node** of the cluster.

## First steps

1. The alert's `missing` label names the absent series. If both are missing, two alerts fire.
2. If it's `consul_catalog_service_node_healthy`, check `up` for the consul_exporter job and the
   exporter's logs.
3. If it's `pg_replication_is_replica`, check `up{env="<env>", type="<type>"}` for the cluster's
   scrape targets, and whether the cluster's `type` label has changed.
4. Until the data is back, watch the cluster directly: `sudo gitlab-patronictl list`.

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-leadership-alerts.libsonnet)
- [Link to edit this playbook](PatroniLeadershipAlertsNoData.md)
