# Container Registry Database Load Balancing

## Background

The Container Registry supports database load balancing. This feature is implemented as described in the [technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md).

You can follow [Container Registry: Database Load Balancing (DLB) (&8591)](https://gitlab.com/groups/gitlab-org/-/epics/8591) for more updates. The rollout plan being followed is detailed [here](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md#rollout-plan).

## Alerts

| Alert | Condition | Duration | Severity |
| ----- | --------- | -------- | -------- |
| [`ContainerRegistryDBHighReplicaPoolChurnRate`](./alerts/ContainerRegistryDBHighReplicaPoolChurnRate.md) | DNS add/remove rate > 0.1/sec | 15m | s3 |
| [`ContainerRegistryDBHighReplicaConnectivityQuarantineRate`](./alerts/ContainerRegistryDBHighReplicaConnectivityQuarantineRate.md) | Connectivity quarantine rate > 0.05/sec | 10m | s3 |
| [`ContainerRegistryDBHighReplicaLagQuarantineRate`](./alerts/ContainerRegistryDBHighReplicaLagQuarantineRate.md) | Lag quarantine rate > 0.05/sec | 5m | s3 |
| [`ContainerRegistryDBReplicaPoolSizeInstability`](./alerts/ContainerRegistryDBReplicaPoolSizeInstability.md) | Pool size stddev > 1 | 5m | s3 |
| [`ContainerRegistryDBReplicaPoolDegraded`](./alerts/ContainerRegistryDBReplicaPoolDegraded.md) | Pool < 50% of 1-day avg | 5m | s3 |
| [`ContainerRegistryDBNoReplicasAvailable`](./alerts/ContainerRegistryDBNoReplicasAvailable.md) | Pool size == 0 | 2m | s2 |
| [`ContainerRegistryDBLoadBalancerReplicaPoolSize`](./alerts/ContainerRegistryDBLoadBalancerReplicaPoolSize.md) | Pool below minimum threshold | 5m | s3/s4 |
| [`PatroniRegistryServiceDnsLookupsApdexSLOViolation`](./alerts/PatroniRegistryServiceDnsLookupsApdexSLOViolation.md) | DNS lookup latency SLO violation | - | s3 |

The first six alerts monitor the replica connectivity tracking and quarantine mechanism introduced in [MR !2596](https://gitlab.com/gitlab-org/container-registry/-/merge_requests/2596). The mechanism protects the load balancer from unstable replicas through:

1. **Consecutive Failure Detection**: Quarantines a replica after 3 consecutive connectivity failures.
1. **Flapping Detection**: Quarantines a replica after 5 add/remove events within a 60-second window.

Quarantined replicas are automatically reintegrated after a 5-minute cooldown period.

## Logs

The list of log entries emitted by the registry is documented [here](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md#logging).

To find all relevant log entries, you can filter logs by `json.msg: "replica" or "replicas" or "LSN"` ([example](https://nonprod-log.gitlab.net/app/r/s/J4dYB)).

## Metrics

The list of Prometheus metrics emitted by the registry is documented [here](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md#metrics).

There are graphs for all relevant metrics in the [registry: Database Detail](https://dashboards.gitlab.net/goto/ulhoLB7NR?orgId=1) dashboard, under a dedicated `Load Balancing` row.

## Related Links

- [Feature epic](https://gitlab.com/groups/gitlab-org/-/epics/8591)
- [Technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-load-balancing.md)
