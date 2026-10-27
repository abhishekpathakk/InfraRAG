# StatefulSet Guidelines

This document will provide a set of guidelines when considering running a
StatefulSet inside of a Kubernetes cluster.  To understand what a StatefulSet
provides, please refer to [the existing Kubernetes StatefulSet
documentation](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

## Guidelines for future use

* We should evaluate all deployment mechanisms that are provided by
  third-parties, whether that be a [Helm Chart](https://helm.sh/) or an
  [operator](https://kubernetes.io/docs/concepts/extend-kubernetes/operator/) if
  possible. The above is usually built by the Maintainers of a project whom have
  a deep understanding of how the service should operate inside of Kubernetes.
  If this is not achievable, then we should have thorough runbooks indicating
  how to handle various failure scenarios that are specific to the service.  The
  [readiness-review] should document what installation methods that already
  exist are evaluated, and what those shortcomings are that prevent us from
  using such.
* We should understand the performance requirements of disk IO for a given
  service.  Kubernetes provides us with a mechanism to choose specific [Storage
  Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) with
  varying degrees of performance.  We'll want to ensure we choose the correct
  disk type given the requirements of the service and what
  [GCP](https://docs.cloud.google.com/compute/docs/disks) provides for us.  [Storage
  Classes] allow for volumes to be dynamically expanded in the future.  We
  should aim to enable [volume
  expansion](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/volume-expansion)
  on persistent disks.
* We should understand the resource demands of the Pods that provide the
  service.  This will help us determine if we should have a dedicated node pool
  for the given service, or leverage bin packing with minimal interruption to
  existing Pods on the same node.
* Understanding the redundancy built into the StatefulSet will govern how we
  manage the service.  Having runbooks that describe how to handle various
  failure scenarios will ensure that we understand what we should expect if we
  experience various failure scenarios and any remediation that must be
  accomplished pending the style of failure that we encounter.
* We should understand what is expected if we experience any data loss.
  Dashboards and alerts shall be configured to allow us to understand if we've
  lost data, had some sort of failure, and runbooks should be created such that
  we know how to handle cases where restoration needs to occur and the risks
  involved in these scenarios.
* We should aim to have data loss scenarios taken into account.  Data should
  either be resistant to some sort of system/zonal failure or we can lose the
  data without fear of interruption of the service itself.  In the former case,
  we'll want to ensure we fully understand how the service behaves and have
  runbooks that lead us down a path to successful recovery of the data.
* Maintenance tasks associated with [Persistent
  Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
  shall be fully understood.  Runbooks associated with the data and or volumes
  necessary for appropriate management of the service shall be created.
* A [readiness-review] is always required to help tease out any use case and
  more thoroughly discuss the above guidelines.

## Current Usage

StatefulSets currently include the following workloads:

* [Prometheus](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/prometheus)
* [Some Redis](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/redis-pubsub)
* [Vault](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/vault)

### Purpose of Stored Data

* Prometheus - Metrics which are scraped and held locally for short term access
  prior to being stored into a Bucket for long term storage
* Redis - Depends on the instance but this is data written to disk to reduce
  sync times between instances in the case of Pod failure
* Vault - Stores the actual encrypted vault data, multiple Pods provide data
  redundancy
* Mimir (compactor, store-gateway) - Long-term metrics storage backing Grafana

Of the above, all data is either okay to have been removed, or redundancy is in
place well enough where if a single Pod where to be lost, the service will
continue to operate well.  Along side this, all of these systems are either
managed by an Operator to ensure the Pods are online enough, or there is a
secondary means of ensuring services remain available while part of the
deployment may not be healthy.

## Considerations

* Ensure that if data is lost, it can easily be recovered.  In the above example
  services, if a persistent volume is lost, the data can be replicated by asking
  the service itself to perform this function in the fashion it is already
  designed to do.  In some cases the data may be temporary, or is a cache, thus
  we may see some slowness, but the data can be rebuilt without any
  administrator action.
* Validate that modifications to configurations can be performed in a safe
  manner.  Services not managed by an Operator may lack some controls for
  validating safe configurations protecting us from the quirks of running
  StatefulSets.  Example; We've had some problems during our initial
  implementation of Redis where we were unable to rollback changes made to a
  deployment because the StatefulSet was in a bad state.  Manual interaction was
  the only course of action of remediation.  We should attempt to avoid this or
  understand this as much as possible such that we have appropriate CI
  notifications or alerts and runbooks in place to fix incident inducing
  situations.
* Consider the tooling that is built on top of existing services.  Accessing
  services through a VM will vary significantly when inside of Kubernetes.
  Ensure these considerations are taken into place and that the tooling works
  for either infrastructure (example during a migration).
* Consider the resource usage of the Pods themselves.  We should consider the
  benchmarking the service to a reasonable extent to validate that we do not
  suffer potential performance issues when running inside of a Kubernetes
  architecture.  Consider any custom tooling, network latency, disk IO
  performance bottlenecks introduced by running the service inside of Kubernetes
  vs. on an VM directly.  If running in Kubernetes is deemed okay, consider
  making use of [Quality of
  Service](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/)
  guarantees.

## Disclaimer

StatefulSets while no longer considered young in the Kubernetes community
manages instances of a service significantly differently that normal
configuration tooling currently does today.  Updates must be thought about in a
very cautious manner and closely monitored to ensure the intended configuration
is indeed in place.  The majority of nodes that manage GitLab.com data are
normally pretty hefty instances.  The sheer size of an instance may not entirely
make sense as the trade-off's of running an instance with the necessary tooling
replicated inside of Kubernetes is not worth it from a long term value
perspective at this moment in time.  The sheer amount of data being managed may
take advantage of special features available to an Operating System that may not
be widely available to Kubernetes.  Think, kernel level tuning or special
sysctls that tune the Operating System for specific efficiencies that may not
yet be [exposed to Kubernetes
clusters](https://kubernetes.io/docs/tasks/administer-cluster/sysctl-cluster/).
And lastly, we started on Virtual Machines. We've built special tooling for
these fleets and a large knowledge base assuming we will continue to leverage on
host capabilities.  Moving this to Kubernetes will certainly involve a lot of
work and planning to carry over any special knowledge, tooling, and new
learnings on a differing Infrastructure.

[readiness-review]: https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production/readiness/
