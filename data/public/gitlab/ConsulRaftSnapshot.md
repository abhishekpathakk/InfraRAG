# ConsulRaftSnapshot

Alerts:

- `ConsulRaftSnapshotJobFailed` (S3, no pager)
- `ConsulRaftSnapshotJobStale` (S2, pages in `ops` and `gprd`)

## Overview

Consul stores its state in a Raft log. An hourly Kubernetes CronJob named
`consul-gl-raft-snapshot` in the `consul` namespace calls
`consul snapshot save` and uploads the file to GCS:

- `gs://gitlab-<env>-consul-snapshots/`

The CronJob and Job pods are defined in
[`services/consul/values-extras.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/consul/values-extras.yaml)
in the `argocd/apps` project.

## Services

- [Consul Service Overview](../README.md)
- Owner: [Fleet Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/fleet-management/)

## Metrics

The alerts read `kube_job_failed` and `kube_cronjob_status_last_successful_time`
from `kube-state-metrics`. The
[Consul dashboard](https://dashboards.gitlab.net/d/consul-main/consul3a-overview)
has a "Last Raft Snapshot Age" stat panel in the top row that turns orange
after 1h05m and red after 2h.

## Alert behavior

### ConsulRaftSnapshotJobFailed

A run of the `consul-gl-raft-snapshot` cronjob entered the `Failed` state.
The next hourly run may recover on its own. The alert posts to
`#f_fleet_alerts` without paging.

### ConsulRaftSnapshotJobStale

No successful snapshot in the last two hours. The cronjob is either failing
repeatedly, suspended, or stuck in `Active`. Pages in `ops` and `gprd`.
Silent in `pre`, `gstg`, and `db-benchmarking`.

## Severities

`ConsulRaftSnapshotJobFailed` is S3 in every environment. A single failed
run does mean a missing snapshot, but the cronjob may just be flaky and
recover on the next hour.

`ConsulRaftSnapshotJobStale` is S2 and pages in `ops` and `gprd`. A two-hour
gap means at least two consecutive missed runs, which is worth looking at.

## Verification

Get the affected environment from the `env` label on the alert, switch
context to that cluster, then:

```sh
glsh kube use-cluster <env>

# Inspect the cronjob and its recent Jobs
kubectl -n consul get cronjob consul-gl-raft-snapshot
kubectl -n consul get jobs --sort-by=.metadata.creationTimestamp \
  | grep consul-gl-raft-snapshot

# Pull logs from the most recent failed Job (both init and main containers)
kubectl -n consul logs job/<job-name> --all-containers=true --prefix=true
```

Check the last successful snapshot in GCS:

```sh
gsutil ls "gs://gitlab-<env>-consul-snapshots/$(date +%Y/%m/%d)/"
```

## Recent changes

- [Recent `argocd/apps` MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged&search=consul)
- [Recent `config-mgmt` MRs](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&state=merged&search=consul)

## Troubleshooting

Common failure modes:

- Consul HTTP endpoint unreachable. The init container hits
  `consul-gl-internal.<env>.gke.gitlab.net:8500`. Check that the Consul
  cluster is healthy and that the internal DNS entry resolves:

  ```sh
  kubectl -n consul run consul-reachability-check --rm -it --restart=Never \
    --image=curlimages/curl:latest -- \
    curl -s "http://consul-gl-internal.<env>.gke.gitlab.net:8500/v1/status/leader"
  ```

  A healthy cluster returns a quoted `"ip:port"` string for the current
  Raft leader.
- GCS upload failure. Check that
  `consul-snapshot@<project>.iam.gserviceaccount.com` still has write access
  to the destination bucket:

  ```sh
  gsutil iam get "gs://gitlab-<env>-consul-snapshots" \
    | jq '.bindings[] | select(.members[] | contains("consul-snapshot@"))'
  ```

  The service account should appear with `roles/storage.objectAdmin` (or an
  equivalent role that grants object write). Check that the Kubernetes
  ServiceAccount used by the CronJob still has the expected Workload
  Identity binding:

  ```sh
  kubectl -n consul get serviceaccount consul-gl-consul-server -o yaml
  ```

  The `iam.gke.io/gcp-service-account` annotation should point at
  `consul-snapshot@<project>.iam.gserviceaccount.com`.
- CronJob suspended. Run:

  ```sh
  kubectl -n consul get cronjob consul-gl-raft-snapshot \
    -o jsonpath='{.spec.suspend}'
  ```

  It should return `false` or empty. If it returns `true`, unsuspend:

  ```sh
  kubectl -n consul patch cronjob consul-gl-raft-snapshot \
    --type=merge -p '{"spec":{"suspend":false}}'
  ```

- Job stuck `Active`. The previous run's pod is still running. Look at it
  with `kubectl -n consul describe job <name>` and delete the Job if it is
  stuck.

## Manual rerun

```sh
kubectl -n consul create job \
  --from=cronjob/consul-gl-raft-snapshot \
  consul-gl-raft-snapshot-manual-$(date +%s)
```

Watch the Job pod until it finishes, then confirm the new snapshot in GCS
using the command above.

## Dependencies

- Consul cluster itself, with the HTTP API reachable.
- GCS bucket write access from the pod's GCP service account.
- `kube-state-metrics` for the alert signal.

## Escalation

If the failure persists after a manual rerun, or if the root cause needs
cluster-wide changes, escalate in `#g_fleet_management` on Slack.

## Definitions

- [Alert definition (libsonnet)](../../../libsonnet/alerts/consul-alerts.libsonnet)
- [Shared raft-snapshot alert helper](../../../libsonnet/alerts/raft-snapshot-cronjob-alerts.libsonnet)
- [CronJob definition (argocd/apps)](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/consul/values-extras.yaml)
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/consul/alerts/ConsulRaftSnapshot.md)

## Related Links

- [Consul interaction guide](../interaction.md)
- [VaultRaftSnapshot](../../vault/alerts/VaultRaftSnapshot.md): the
  equivalent alert for Vault.
