# Prometheus pod crashlooping

A Prometheus Kubernetes pod is crashlooping.

## Common symptoms

### Out of memory

Increase the memory in the Prometheus values: <https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/prometheus>

Ensure that we have enough cluster-level headroom to accommodate this. As of
today, there is no simple, single procedure to ensure this.

### Persistent disk full

This is actually often a symptom of OOM kills: the crashlooping process will
begin to write out some WAL on each boot, until the disk is full.

Mitigations:

```
# Open an ssh tunnel to the relevant cluster
glsh kube use-cluster gprd

# Get a shell on a container that has access to the volume. If prometheus itself
# is down for a long crashloop, you can use thanos-sidecar:
kubectl -n monitoring exec -it prometheus-gitlab-monitoring-promethe-prometheus-1 -c thanos-sidecar sh

# In that pod shell:
df -h

# Clean out temporary dirs, **only if the prometheus container is indeed not
# running**
rm -rf /prometheus/*.tmp

# Check the disk usage again:
df -h

# As a last resort, delete some WAL. This will cause data loss of metrics
# ingested since the last commit on this replica. This might be acceptable, as
# we can rely on our hopefully-healthy redundant replica(s) to retain this data
# and ship it to thanos.
rm -rf /prometheus/wal/*
```

### Remove corrupted WAL files

On occasion the WAL files will become corrupted as they did in [incident 6148](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/6148) and [incident 5998](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/5998).

There are a few things to check to determine if the WAL files are corrupted.

- Run du -h and confirm that wal is large and chunks_head is also huge
- Tail the logs on the pod to confirm it was recovering WALs when it was killed
- Search the logs for "iterate on on-disk chunks" and look for errors ([example](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/6148#note_806559414))

The resolution to this was to delete the WAL files as below:

```
 ~ kubectl -n monitoring exec -it prometheus-gitlab-monitoring-promethe-prometheus-0 -c thanos-sidecar -- sh
/ $ cd /prometheus/
/prometheus $ rm -rf wal/
```
