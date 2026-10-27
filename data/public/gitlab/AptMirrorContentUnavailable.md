# AptMirrorContentUnavailable

## Overview

No content replicas are available for the internal apt mirror, so
`https://apt-mirror.<env>.gke.gitlab.net` is not answering. See
[the apt mirror runbook](../README.md).

There is no user-facing impact: the mirror serves packages to our own VMs, not
traffic. The impact is on configuration management. Every VM whose apt source
points at the mirror fails `apt-get update`, `apt_update` runs early in the
chef-client run, and a failure there aborts the whole run — so nodes stop
converging entirely, not just for packages. The HAProxy fleets resolve through
the mirror today, with other fleets moving across as they are cut over.

## Services

- [Service Overview](../README.md)
- Owner: Production Engineering: Fleet Management
- Alerts channel: `#f_fleet_alerts`

## Diagnosis

`kubectl` reaches these clusters through the console server, not a bastion:

```shell
glsh kube use-cluster gprd   # or gstg
kubectl -n apt-mirror get deploy,statefulset,pod
```

Content serving depends on the database and on object storage, so check those
before the content pods themselves:

```shell
kubectl -n apt-mirror get statefulset apt-mirror-pulp-database
kubectl -n apt-mirror logs deploy/apt-mirror-pulp-content --tail=100
kubectl -n apt-mirror describe deploy apt-mirror-pulp-content
```

Confirm whether nodes are actually failing, rather than assuming from the
alert. In Mimir for that environment:

```promql
chef_client_error{env="gprd", fqdn=~"haproxy-.*"}
```

And from any VM in that environment:

```shell
curl -sL -o /dev/null -w '%{http_code}\n' \
  https://apt-mirror.gprd.gke.gitlab.net/pulp/content/haproxy/jammy/dists/jammy/InRelease
```

## Remediation

- If the database statefulset is not ready, fix that first. Content cannot
  serve without it.
- Content pods sometimes need deleting rather than restarting:

  ```shell
  kubectl -n apt-mirror delete pod -l app.kubernetes.io/name=pulp-content
  ```

  Do not use `kubectl rollout restart` on these workloads. The Pulp operator
  owns the `repo-manager.pulpproject.org/restartedAt` annotation and reverts it.
- Check the app in ArgoCD. If the deployment was scaled to zero or pruned by a
  sync, the fix is in
  [`services/apt-mirror/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/apt-mirror)
  rather than in the cluster.
- If content cannot be restored quickly, take the affected roles back to their
  upstream sources by removing the `keyring` and mirror `uri` attributes from
  the role in chef-repo. Be clear about the timescale: that is a merge plus an
  apply plus a converge on each node, so minutes at best, and nodes keep
  failing their runs until it lands. Restoring the mirror is usually faster.
- Verify recovery with the `curl` above returning 200, then confirm
  `chef_client_error` clears as nodes converge on their own interval.
