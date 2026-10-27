# VaultRaftSnapshot

Alerts:

- `VaultRaftSnapshotJobFailed` (S3, no pager)
- `VaultRaftSnapshotJobStale` (S2, pages in `ops`)

## Overview

Vault stores its data in a Raft-backed integrated storage engine. An hourly
Kubernetes CronJob named `vault-raft-snapshot` in the `vault` namespace calls
`vault operator raft snapshot save` and uploads the `.snap` file to GCS:

- Production (`ops` env): `gs://gitlab-vault-production-vault-raft-snapshots/`
- Staging (`pre` env): `gs://gitlab-vault-staging-vault-raft-snapshots/`

The CronJob and Job pods are defined in
[`services/vault/values-extras.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/vault/values-extras.yaml)
in the `argocd/apps` project.

## Services

- [Vault Service Overview](../README.md)
- Owner: [Fleet Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/fleet-management/)

## Metrics

The alerts read `kube_job_failed` and `kube_cronjob_status_last_successful_time`
from `kube-state-metrics`. The
[Vault dashboard](https://dashboards.gitlab.net/d/vault-main/vault3a-overview)
has a "Last Raft Snapshot Age" stat panel in the top row that turns orange
after 1h05m and red after 2h.

## Alert behavior

### VaultRaftSnapshotJobFailed

A run of the `vault-raft-snapshot` cronjob entered the `Failed` state. The
next hourly run may recover on its own. The alert posts to `#f_fleet_alerts`
without paging.

### VaultRaftSnapshotJobStale

No successful snapshot in the last two hours. The cronjob is either failing
repeatedly, suspended, or stuck in `Active`. Pages in `ops`. Silent in
`pre`.

## Severities

`VaultRaftSnapshotJobFailed` is S3 in every environment. A single failed
run does mean a missing snapshot, but the cronjob may just be flaky and
recover on the next hour.

`VaultRaftSnapshotJobStale` is S2 and pages in `ops`. A two-hour gap means
at least two consecutive missed runs, which is worth looking at.

## Verification

Get the affected environment from the `env` label on the alert, switch
context to that cluster, then:

```sh
glsh kube use-cluster <env>

# Inspect the cronjob and its recent Jobs
kubectl -n vault get cronjob vault-raft-snapshot
kubectl -n vault get jobs \
  -l app.kubernetes.io/component=vault-raft-snapshot \
  --sort-by=.metadata.creationTimestamp

# Pull logs from the most recent failed Job (both init and main containers)
kubectl -n vault logs job/<job-name> --all-containers=true --prefix=true
```

Check the last successful snapshot in GCS:

```sh
# ops: gitlab-vault-production-vault-raft-snapshots
# pre: gitlab-vault-staging-vault-raft-snapshots
gsutil ls "gs://gitlab-vault-<production|staging>-vault-raft-snapshots/$(date +%Y/%m/%d)/"
```

## Recent changes

- [Recent `argocd/apps` MRs](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests?scope=all&state=merged&search=vault)
- [Recent `config-mgmt` MRs](https://gitlab.com/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&state=merged&search=vault)

## Troubleshooting

Common failure modes:

- Vault login failure. The CronJob uses the `raft-snapshots` GCP auth role.
  Check that the `vault-active` Kubernetes Service is reachable from inside
  the `vault` namespace:

  ```sh
  kubectl -n vault run vault-reachability-check --rm -it --restart=Never \
    --image=curlimages/curl:latest -- \
    curl -sk https://vault-active:8200/v1/sys/health
  ```

  A healthy active node returns HTTP 200 with `"initialized":true` and
  `"sealed":false`.

  Verify the `raft-snapshots` GCP auth role still exists and lists the
  expected service account (run against the affected env with a suitable
  Vault token):

  ```sh
  vault read auth/gcp/role/raft-snapshots
  ```

  The `bound_service_accounts` field should include
  `vault-<env>-k8s@<project>.iam.gserviceaccount.com`.

  Check that the Kubernetes ServiceAccount used by the CronJob still has
  the expected GCP identity annotation (Workload Identity binding):

  ```sh
  kubectl -n vault get serviceaccount vault -o yaml
  ```

  The `iam.gke.io/gcp-service-account` annotation should point at
  `vault-<env>-k8s@<project>.iam.gserviceaccount.com`.
- GCS upload failure. Check that the Google service account
  `vault-<env>-k8s@<project>.iam.gserviceaccount.com` still has write access
  to the destination bucket:

  ```sh
  # ops: gitlab-vault-production-vault-raft-snapshots
  # pre: gitlab-vault-staging-vault-raft-snapshots
  gsutil iam get "gs://gitlab-vault-<production|staging>-vault-raft-snapshots" \
    | jq '.bindings[] | select(.members[] | contains("vault-"))'
  ```

  The service account should appear with `roles/storage.objectAdmin` (or an
  equivalent role that grants object write).
- CronJob suspended. Run:

  ```sh
  kubectl -n vault get cronjob vault-raft-snapshot \
    -o jsonpath='{.spec.suspend}'
  ```

  It should return `false` or empty. If it returns `true`, unsuspend:

  ```sh
  kubectl -n vault patch cronjob vault-raft-snapshot \
    --type=merge -p '{"spec":{"suspend":false}}'
  ```

- Job stuck `Active`. The previous run's pod is still running. Look at it
  with `kubectl -n vault describe job <name>` and delete the Job if it is
  stuck.

## Manual rerun

```sh
kubectl -n vault create job \
  --from=cronjob/vault-raft-snapshot \
  vault-raft-snapshot-manual-$(date +%s)
```

Watch the Job pod until it finishes, then confirm the new snapshot in GCS
using the command above.

## Dependencies

- Vault cluster itself, with the `vault-active` Kubernetes Service
  reachable.
- GCP auth backend and the `raft-snapshots` role.
- GCS bucket write access from the pod's GCP service account.
- `kube-state-metrics` for the alert signal.

## Escalation

If the failure persists after a manual rerun, or if the root cause needs
cluster-wide changes, escalate in `#g_fleet_management` on Slack.

## Definitions

- [Alert definition (libsonnet)](../../../libsonnet/alerts/vault-alerts.libsonnet)
- [Shared raft-snapshot alert helper](../../../libsonnet/alerts/raft-snapshot-cronjob-alerts.libsonnet)
- [CronJob definition (argocd/apps)](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/vault/values-extras.yaml)
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/vault/alerts/VaultRaftSnapshot.md)

## Related Links

- [Vault overview](../vault.md)
- [Vault troubleshooting](../troubleshooting.md)
- [ConsulRaftSnapshot](../../consul/alerts/ConsulRaftSnapshot.md): the
  equivalent alert for Consul.
