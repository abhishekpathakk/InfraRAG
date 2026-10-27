# Kubernetes runner managers

A growing share of the runner fleet's managers runs as Kubernetes
Deployments on GKE, managed by ArgoCD. Nothing on this page involves Chef,
knife, or SSH to a
manager: the manager is a pod, its configuration is Helm values in git, and
all changes go through merge requests.

The ephemeral job VMs are unchanged: the manager pod runs the same
`docker+machine` executor and provisions the same COS VMs as the Chef-based
managers. Everything in the [debugging guide](debugging.md) about job VMs and
their connectivity still applies once you are inside the manager pod.

Background and rationale live in the
[design document](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/runner_managers_kubernetes/)
and the [central cluster epic](https://gitlab.com/groups/gitlab-com/gl-infra/ci-runners/-/work_items/29).

## Layout

One manager cluster per environment. All manager pods for an environment run
on it; the ephemeral VMs stay in their per-project networks and never move.

| Cluster | Environment label | Application suffix |
| --- | --- | --- |
| `runner-managers-gprd-1` | `gprd-ci` | `671a4` |
| `runner-managers-gstg-1` | `gstg-ci` | `05283` |
| `runner-managers-dev-1` | `dev-ci` | `b03bb` |
| `runner-managers-ops-1` | `ops-ci` | `cf88e` |

All in project `gitlab-ci-155816`, regional in `us-east1`, on the ci
network, defined as explicit resources in
[`config-mgmt/environments/ci/gke-runner-managers.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ci/gke-runner-managers.tf).
The application suffix is the hash ArgoCD appends to the cluster's
Application names. Each cluster's ArgoCD secret has
`gitlab.com/runner-cluster: "true"`, which services use to exclude runner
clusters without listing them.

A shard is a directory under
[`services/gitlab-runner/env/gprd-ci/shards/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/gitlab-runner/env/gprd-ci/shards),
and each shard spans one or more ephemeral VM projects. One manager
Deployment exists per shard-project pair. The shard directory list is the
inventory; examples of the naming pattern:

| Shard | Runner | VM projects |
| --- | --- | --- |
| `p-s` | `k8s.private...gitlab.com/gitlab-org` | `gitlab-r-saas-l-p-amd64-{1..9}` |
| `p-com` | `k8s.private...gitlab.com/gitlab-com` | `gitlab-r-saas-l-p-amd64-{1..9}` |
| `l-s-amd64` | `k8s.saas-linux-small-amd64...default` | `gitlab-r-saas-l-s-amd64-{1..9}` |
| `l-m-arm64` | `k8s.saas-linux-medium-arm64...default` | `gitlab-r-saas-l-m-arm64-{1..5}` |

The private shards keep their deployed shorthand names. New shards are named
after their ephemeral project family minus the `saas-` prefix (`l-s-amd64`,
`l-m-arm64`, ...).

| What | Where |
| --- | --- |
| Namespace | `gitlab-runner` |
| Deployments | one per shard-project: `gitlab-runner-<shard>-<project>` |
| ArgoCD service | [`services/gitlab-runner/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/gitlab-runner) in `argocd/apps` |
| Shared objects | [`services/gitlab-runner-commons/`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/gitlab-runner-commons) |
| Values | `services/gitlab-runner/env/gprd-ci/shards/<shard>/` and `.../clusters/<cluster>/` |
| ArgoCD UI | <https://argocd.gitlab.net/> (applications `gitlab-runner--<shard>--<project>--<cluster hash>`) |
| Chart | `gitlab-runner` Helm chart, version pinned per shard-cluster in `projects.yaml` |

Unlike most services, gitlab-runner is not rendered by the generic-services
ApplicationSet. The
[`argocd-runner-managers` chart](https://gitlab.com/gitlab-com/gl-infra/charts/-/tree/main/gitlab/argocd-runner-managers)
(rendered by `applications/gitlab-runner.yaml`) creates three ApplicationSets:

- **per project**: shard-cluster directories with a `projects.yaml` get one
  runner Application per project, `1` through `projectCount`. The TOML derives
  all GCP fields from the project number
  (`google-project={{ .Values._projectPrefix }}{{ .Values._project }}`), so a
  shard's projects share one values file and adding a project is a one-line
  count bump.
- **per shard**: one secrets Application per shard-cluster
  (`gitlab-runner--<shard>--secrets--<hash>`) renders the shard's
  ExternalSecrets, independent of the project count.
- **per cluster**: directories with a legacy `app.yaml` instead of a
  `projects.yaml` get the old one-Application-per-cluster layout. The
  `deployer` and `gvisor-*` shards in `env/ci` still use it.

Cluster-shared objects are owned by the `gitlab-runner-commons` service (a
normal generic service): the `runner-manager` ServiceAccount all manager pods
run as, the `gitlab-runner-secrets` SecretStore, the external-secrets
ServiceAccount and RBAC, and the registry pull secret. No shard's Application
owns anything another shard needs.

Each shard-project deployment runs several replicas that share one runner
token, so they appear as a single runner in GitLab with multiple
`system_id`s. Capacity settings (`concurrent`, `limit`, `IdleCount`) are per
replica; deployment capacity is the per-replica value times `replicas`.

Sizing a shard's runner config:

- `concurrent` is the job capacity per pod. Multiply by `replicas` for the
  per-project capacity, then multiply that by `projectCount` for the
  shard's total.
- `limit` = `concurrent` plus slack for machines mid-replacement. For
  docker+machine, `limit` caps total machines including ones being created
  and removed, and jobs are only accepted when a warm machine exists. At
  `MaxBuilds` 1 every job replaces its machine, so a steady share of
  `limit` is always mid-lifecycle: Chef sizes that at about 8 percent. At
  `MaxBuilds` 40 churn is a fortieth of that, and IdleCount-sized slack is
  plenty.
- `request_concurrency` decides the job share against other managers
  polling the same token, independent of capacity. Keep it proportional
  when splitting capacity across fleets.
- `IdleCount` is the warm pool per pod. Copy the legacy shard's value; they
  were tuned per worker.

## Mapping a job to a manager pod

The job log names the runner:

```plaintext
Running with gitlab-runner 18.5.0~pre... on
k8s.private.runners-manager.gitlab.com/gitlab.com/gitlab-org/medium Jn8J2S38P, system ID: r_...
```

The runner name maps to a shard by the naming pattern (this one is `p-m`), and
the VM name in the job log contains the project number. To find the specific
pod for a `system_id`, check the `system_id` label on the runner metrics or
grep the pods' logs.

## Access and logs

```bash
glsh kube use-cluster runner-managers-gprd-1

kubectl get pods -n gitlab-runner
kubectl logs -n gitlab-runner deploy/gitlab-runner-p-s-1 --since=1h
```

Logs are JSON and also ship to Elasticsearch through the same pipeline as the
VM fleet (`pubsub-runner-inf-gprd-*`, filter on `json.shard`).

## Debugging ephemeral VM creation

The equivalent of running `docker-machine` on a manager VM is exec-ing into
the manager pod. Machine state and certificates live in the pod filesystem:

```bash
POD=$(kubectl get pods -n gitlab-runner -l app=gitlab-runner-p-s-1 -o name | head -1)
kubectl exec -it -n gitlab-runner ${POD#pod/} -- sh

# inside the pod
docker-machine ls
docker-machine ssh runner-xxxxxxxx-private-...
```

From inside a job VM the connectivity checks from the
[debugging guide](debugging.md#part-2-testing-ephemeral-vm-connectivity) apply
unchanged.

Every pod runs a boot_verify canary at startup: it creates and deletes one VM
before the readiness endpoint (`/health/ready` on port 9252) reports healthy,
and the Deployment's startupProbe waits for it. A pod stuck `0/1 Running` with
restarts means VM provisioning is broken; check its logs for the failing
create step before anything else.

### Ready does not mean polling

boot_verify proves the manager can provision a VM and run a job on it. Job
polling is a different endpoint (ci-gateway) through a different network path,
and it is not covered: a manager with a broken path to ci-gateway reports
Ready indefinitely while every job request times out. If a Ready manager runs
no jobs, check its logs for job request errors before suspecting capacity or
queueing.

### Auth failures look like missing projects

The pods authenticate to GCP through Workload Identity: they all run as the
`runner-manager` ServiceAccount (owned by gitlab-runner-commons), and the
GCP-side binding lives in
[`config-mgmt/environments/ci/runner-managers.tf`](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ci/runner-managers.tf).
A missing binding does not produce a permission error: GCP returns
`Project with ID "..." not found` on the pre-create check. If a new or renamed
deployment fails like this, check the binding before anything else.

## Configuration changes, deploys, rollbacks

All configuration lives under
`services/gitlab-runner/env/gprd-ci/shards/<shard>/`:

- `values.yaml` (shard level): everything shared across clusters
- `clusters/<cluster>/values.yaml`: replicas, resources, and the full
  `config.toml` as `runners.configOverride`
- `clusters/<cluster>/projects.yaml`: chart version pin, `projectCount`,
  `projectPrefix`
- `clusters/<cluster>/values-vault-secrets.yaml`: the shard's
  ExternalSecrets

`runners.configOverride` is templated by the runner chart, which is how the
per-project GCP fields work. `envVars` values are **not** templated; a
template expression there ships to the pod literally.

Change process is a merge request. After merging, the ApplicationSet's
[progressive RollingSync](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Progressive-Syncs/)
rolls the change out automatically; expect minutes of delay, or sync the
application in the ArgoCD UI to expedite. Rollback is a revert MR.

Do not edit resources with kubectl: ArgoCD reverts drift on the next sync,
and git stops matching what actually runs.

Deploys rotate pods with `maxSurge: 100%` / `maxUnavailable: 0` and long
termination grace periods sized to each shard's max job timeout. A deploy
therefore keeps the old generation draining for hours; both generations
polling at once is normal, as are 409 conflicts on `jobs/request` (replicas
racing on the shared token).

The manager image is pinned by digest-tagged version in values. Never use the
floating `bleeding` tag: it derives a helper image tag that is never
published, which breaks the boot_verify canary.

## Operational controls

- **Pause the runner** in the target instance's
  [admin runners list](https://gitlab.com/admin/runners?runner_type%5B%5D=INSTANCE_TYPE):
  new job assignment stops within one poll interval, running jobs finish.
  One runner record covers all of a shard's deployments and replicas, so
  this pauses the whole shard at once. While the Chef fleet exists, its
  runners share the queue and take the jobs.
- **Scale to zero**: `replicas: 0` in the shard-cluster values, per
  shard-project deployment. Graceful (pods drain jobs and delete their
  machines) and git-tracked, but takes an MR plus up to the shard's job
  timeout to complete.
- **Capacity and resources**: `concurrent`, `limit`, `IdleCount`, replica
  count, and pod resources all live in the shard's values (see
  [configuration changes](#configuration-changes-deploys-rollbacks) and
  the sizing guide above).
- **Observability**: the
  [CI Runners dashboards](https://dashboards.gitlab.net/dashboards/f/ci-runners/)
  in Grafana and manager logs in Kibana (`pubsub-runner-inf-gprd-*`,
  filter on `json.shard`); see [health signals](#health-signals).
- **During the migration**: the Chef runners carry `<family>-legacy` tags
  (`saas-linux-small-amd64-legacy`), letting a job pin itself to the Chef
  fleet. Useful as a customer-facing workaround when a k8s-side regression
  is suspected. The tags are removed together with the Chef managers.

Pausing or scaling to zero removes the k8s share of the shard's capacity.
Where Chef limits were reduced to make room for k8s raises, the Chef
managers cannot serve the full load: raise their `limit` and `concurrent`
back to match, or jobs may queue.

## Secrets

Runner tokens and the Sentry DSN come from Vault via External Secrets:

- Tokens are per shard and shared by all of the shard's deployments, at
  `k8s/env/<env>/gitlab-runner/shards/<shard>`; check the shard's
  `values-vault-secrets.yaml` for the path and property.
- The shard's secrets Application renders them into
  `gitlab-runner-<shard>-secret`, using the SecretStore and external-secrets
  objects owned by gitlab-runner-commons.

ExternalSecrets with `refreshInterval: 0` never re-fetch: a changed
`remoteRef` (new path, new property) needs a manual delete of the target
secret before it picks up the new value. The runner secrets use `15m`, but
the risk applies to anything copied from older definitions.

## Health signals

- Pod ready = boot_verify passed. `kubectl get pods -n gitlab-runner`. But
  see "Ready does not mean polling" above.
- `gitlab_runner_jobs` vs `gitlab_runner_limit` per instance: pinned at limit
  means the deployment is saturated (harmless for shards still sharing a
  token with Chef managers: the shared queue sends excess jobs there).
- `gitlab_runner_worker_processing_failures_total{failure_type="no_free_executor"}`:
  poll attempts that found no warm machine. Routine at low rates; sustained
  high rates during steady state mean the idle pool cannot keep up.
- `gitlab_runner_autoscaling_machine_states`: warm pool depth per state.
- Shard-level saturation: `gitlab_component_saturation:ratio{component="private_runners"}`
  (jobs over limits summed across the shard, VM and k8s managers together).

Metrics flow through the monitoring stack on the cluster to the
environment's Mimir tenant (`gitlab-gprd` for gprd), stamped with the same
labels as the VM fleet (`environment`, `shard`, `worker`, plus `cluster`).
The [CI Runners dashboards](https://dashboards.gitlab.net/dashboards/f/ci-runners/)
graph all of the above; deploy annotations mark k8s rollouts on the
overview. k8s-monitoring-stack rolls out through RollingSync like the
runner service; sync it in the UI to expedite a scrape config change.

## Adding a project to a shard

The cheap operation, once the VM project itself exists: the project half
of [provisioning a new shard](new-shards.md) (quota, CIDRs, network,
`env-projects` module) is unchanged.

1. Bump `projectCount` in the shard's `projects.yaml`.
2. Bump the family's count in the reaper manifest
   (`services/reaper/manifests/main.jsonnet`): its project list is
   separate from `projectCount`, and a project missing there gets no
   orphaned-VM cleanup.
3. If Chef managers still serve the shard, reduce their capacity for the
   same project by the amount added, keeping the project total level.
   Merge the k8s change first.
4. Verify the new deployment before relying on it: a real job completed,
   Mimir series carry `shard` and `worker` labels, logs in Elasticsearch.

## Adding a shard

1. Store the shard's runner token in Vault. When creating the runner in
   Rails, copy the cost factors from the equivalent Chef runner: they
   default to 1.0, which undercharges every family above small.
2. New directory under `services/gitlab-runner/env/gprd-ci/shards/`, named
   after the ephemeral project family minus `saas-`. Copy the closest
   existing shard and diff every setting against its current source of truth
   (the Chef shard config, or the donor shard), justifying each difference.
3. `projects.yaml` with the chart version, `projectPrefix`, and
   `projectCount: 1`, plus the token ExternalSecret in
   `values-vault-secrets.yaml`.
4. Start with `concurrent = 1` and `limit` low, verify (real job, metrics
   labels, logs, vector and wiz clean), then raise to sized capacity.

No infrastructure work: the ServiceAccount, SecretStore, Workload Identity,
vector, and monitoring all exist at cluster level. A shard built on a new
VM project family also needs a families entry in the reaper manifest
(see adding a project above).

## Adding a cluster

The rare operation: a second cluster in an environment, or the first
cluster of a new one. A cluster in an existing environment
(`runner-managers-gprd-2`)
reuses the environment's vault secrets, Sentry DSN, wiz secrets,
observability tenant, AppProject, and Workload Identity binding. A new
environment needs all of those created first.

1. **config-mgmt** (`environments/ci`): subnet with secondary ranges,
   cluster and node pools (copy `gke-runner-managers.tf`), the pods range in
   the docker-machine firewalls and in the environment's ci-gateway
   firewall, a vector account for the environment's log topic. The
   account's publish grant lives in the runner environment's
   `pubsub_loggers`, a separate apply in a separate environment.
   Keep node pool names short: GKE truncates cluster+pool in node names,
   which breaks node-family selectors.
2. **config-mgmt again, after the cluster applies**: the vault auth entry
   in `environments/vault-production` (it reads the cluster-info secret,
   which exists only once the cluster does). Clusters in a new GCP project
   also need AppProject destinations in argocd/config (the existing ones
   wildcard on the project) and a runner-manager Workload Identity member
   (the binding is per workload pool, so same-project clusters are already
   covered). New environments also need the vault secret tree
   (`k8s/env/<env>/gitlab-runner/...`: shard tokens, sentry, wiz) and an
   observability tenant whose environment label matches; copying another
   environment's tenant labels every metric with the wrong environment.
3. **Allowlist.** The pods range goes in `allowlisted_runner_managers` in
   `<env>-base-haproxy-ci.json` in chef-repo: without it the ci-gateway
   307-redirects the job API to the public entrypoint, which mostly works,
   so nothing obviously breaks.
4. **argocd/config**: register the cluster (endpoint, CA, labels).
   `gitlab.com/stage` must be exactly `prod` or `non-prod`: any other
   spelling drops the cluster's apps into the serial catch-all RollingSync
   step and stalls every service's prod rollout.
5. **runbooks**: the new ranges (nodes and services /20s, a pods range) in
   the [subnet allocations registry](../../uncategorized/subnet-allocations.md),
   and a `kubernetes/clusters.json` entry for `glsh kube use-cluster`.
6. **argocd/apps**: an `app.yaml` for gitlab-runner-commons and for
   k8s-monitoring-stack under the new cluster, then per shard a
   `projects.yaml` (and values file if anything differs from the shard
   level).
7. **Verify before raising capacity**: a real job completed, a
   `POST /api/v4/jobs/request` from a manager pod to the gateway returns
   400 rather than a 307 redirect, Mimir series carry `cluster`, `shard`,
   and `worker` labels, logs queryable in Elasticsearch, vector and wiz
   error-free. None of these alert when broken. Vector drops what it cannot
   publish, so log gaps do not backfill.

## Removing a deployment or cluster

Order matters.

1. **Scale to zero first** (`replicas: 0`), do not delete: pods drain their
   jobs and delete their machines on shutdown, and rollback is a revert.
2. **Delete the Applications before deleting their files.** The
   ApplicationSets run `applicationsSync: create-update`: removing a values
   file orphans the Application, which then renders chart defaults (3
   replicas, no config) and crashloops. Cascade-delete the apps, then merge
   the file removal.
3. Cluster teardown in config-mgmt: keep the kubernetes provider alive on a
   `data google_container_cluster` source for the destroy apply (`removed`
   blocks cannot forget resources inside an implicitly-destroyed module),
   and remove it in a follow-up. On Shared VPC, delete clusters **before**
   removing their host-project IAM: the GKE robots need
   `container.hostServiceAgent.use` on the host project to delete, not just
   to create. Subnets delete only after nodes and the control plane's PSC
   endpoints are gone; a failed subnet delete right after cluster deletion
   is usually a race against GKE's async cleanup, retry.
4. **Deregister everywhere registrations were added**: the cluster secret
   in argocd/config (nothing prunes it, and a stale registration keeps
   generating Applications for every service), the vault auth entry, the
   `kubernetes/clusters.json` entry, and the pods range in
   `allowlisted_runner_managers` in chef-repo.
5. **Sweep orphaned VMs after the cluster is gone**: filter on the
   `runner_manager_cluster` label, which holds the cluster name
   (`runner_manager_name` is the manager pod name). Do not sweep earlier; see
   the Terminating-pod pitfall below.

## Pitfalls

- **Never force-delete a runner pod.** The termination grace period is the job
  drain, and the pod deletes its machines on shutdown. Force-deleting orphans
  the VMs and fails the jobs on them.
- **A pod stuck Terminating past its grace period with an unreachable
  kubelet is not a stuck deletion.** The shutdown signal may never have been
  delivered: manager pods in that state can keep polling, running jobs, and
  creating VMs while Kubernetes shows them Terminating. Check the
  VM project for machines with recent creation timestamps and the pod's
  manager label before treating the pod as dead.
- **RollingSync-triggered syncs prune with `syncPolicy.automated.prune` even
  when automated sync is disabled.** The runner service sets
  `prune: false` explicitly for this reason; do not remove it, and do not
  rely on "automated sync is off" to protect shared resources anywhere else.
- **A new cluster's first sync can deadlock.** RollingSync stops on a
  Degraded application while the application that would heal it waits in a
  later step. Sync the blocked application manually once; healthy clusters
  do not hit this.
- **One ownership conflict freezes the whole ApplicationSet.** If an
  Application already exists with a different owner, the ApplicationSet
  stops reconciling all of its Applications, not just that one. Delete the
  conflicting Application and force ApplicationSet reconciliation with an
  annotation.
- **A deletion stuck on an in-flight sync** can be cleared by removing the
  operation:
  `kubectl -n argocd patch application <name> --type json -p '[{"op":"remove","path":"/operation"}]'`.
- Services that must not run on runner clusters exclude the
  `gitlab.com/runner-cluster` label (`DoesNotExist`) instead of maintaining
  name lists; the label exists from the moment the cluster registers, so
  there is no window for stray Applications.
- Manager node pools use autoscaled blue-green upgrades with
  `safe-to-evict: "false"` pods: node drains wait for pod rotation instead of
  evicting mid-job. Do not force-drain manager nodes; jobs up to the full
  grace period are running on the pods.
- `google-flex-selection` requires `google-bulk-insert`. The error surfaces
  only on real VM creation, as boot_verify failures on an otherwise clean
  deploy.
- Monitoring failures are silent by default: an empty relabel capture group
  drops labels without errors, and vector publishes to nonexistent pubsub
  topics with only pod-log errors to show for it. After any change to the
  monitoring values, confirm the series and labels actually arrive.
- ApplicationSet generator behaviour differs across ArgoCD versions
  (selectors especially). Verify chart changes against the deployed
  controller version, not the docs; the diff preview is the integration
  test.
- The `omnibus` shards (`gitlab-r-omnibus-build-runners`) are the only
  runner VMs in the fleet with **external IPs and a driver-created firewall
  rule** (`0.0.0.0/0` on 22/2376, SSH keys and TLS client certificates): their machine options omit
  both `google-use-internal-ip` and `google-skip-firewall-create`, unlike
  every other shard. This matches the original chef design
  ([chef-repo!7715](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/7715)),
  which never ran, so there is no operational history behind it. It is
  deliberate (the `omnibus-build-runners` network is not peered with the
  ci-gateway and reaches `gitlab.com` over public egress), but flag it to
  infrasec proactively rather than waiting for Wiz to find it.
