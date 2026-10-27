# Kubernetes on-call setup

Complete these steps before your first on-call shift with cluster access.

Cluster config lives across a handful of repositories — see [Where things live](kubernetes.md#where-things-live) in the Kubernetes overview.

CI jobs on `ops.gitlab.net` apply changes. Deployer changes some cluster state outside git — the CI job that applied a given change is your audit trail.

## Kubernetes API access

Our GKE clusters are private. Access requires either the corporate VPN or an SSH tunnel via bastion.

### Prerequisites

1. [Set up Yubikey SSH keys](../uncategorized/yubikey.md).
2. [Set up bastion access](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/bastions).
3. Install `gcloud`: <https://docs.cloud.google.com/sdk/docs/install-sdk>.
4. Install the GKE auth plugin: `gcloud components install gke-gcloud-auth-plugin`. See [Bind kubectl to GKE](https://cloud.google.com/blog/products/containers-kubernetes/kubectl-auth-changes-in-gke).
5. Install `kubectl` — [macOS](https://kubernetes.io/docs/tasks/tools/install-kubectl-macos/), [Linux](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).
6. `gcloud auth login`.

If you see permission warnings under `~/.config/gcloud/`, fix ownership: `sudo chown -R "$(whoami)" ~/.config`.

### Option A: VPN

1. `glsh kube setup --no-proxy` — writes kubeconfig entries for all clusters without a proxy. See [`glsh`](../../README.md#running-helper-scripts-from-runbook).
2. Launch NordLayer and [connect to one of the organization gateways](https://handbook.gitlab.com/handbook/security/corporate/systems/vpn/setup/#nordlayer-for-system-administration) — not to a shared gateway.
3. Pick a cluster: `glsh kube use-cluster` lists them; `glsh kube use-cluster gstg --no-proxy` selects one. `kubectx` also works.
4. Confirm: `kubectl get nodes`.

### Option B: SOCKS5 proxy via SSH

1. `glsh kube setup` — writes kubeconfig entries with the SOCKS5 proxy configured.
2. `glsh kube use-cluster gstg`.
3. In a separate window, `kubectl get nodes`.

### GUI and terminal UIs

Optional but handy:

- [k9s](https://k9scli.io/) — terminal UI over the local kubeconfig; fast for browsing pods, logs, events, and resource usage during an incident.
- [Lens IDE](https://lenshq.io/products/lens-k8s-ide) — desktop GUI over the local kubeconfig.
- The [GKE console](https://console.cloud.google.com/kubernetes) shows most of the same information in a browser.

Metrics and dashboards: <https://dashboards.gitlab.net/dashboards/f/kubernetes/kubernetes>.

## Shell access to nodes and pods

### Node access via IAP

```sh
kubectl get pods -o wide   # get the node name
gcloud compute --project gitlab-production ssh <node> --tunnel-through-iap
```

You may receive a SIRTBot notification. GKE COS nodes run [`containerd`](https://containerd.io/); use `crictl` for container operations:

```sh
crictl ps
crictl exec -u root -it <container> /bin/bash
```

Do not install packages directly on the node. Use `toolbox` (see [k8s-operations.md](k8s-operations.md#toolbox-on-the-node)) or an ephemeral debug container instead:

```sh
kubectl debug -it <pod> --image=busybox --target=<pod>
```

See [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/).

### Pod access

```sh
kubectl exec -n <namespace> -it <pod> -- sh
```

Some images lack a shell — use `kubectl debug` instead.

## Local `k-ctl` for `k8s-workloads/gitlab-com`

`k-ctl` is a shell wrapper over `helmfile` used **only** by [`k8s-workloads/gitlab-com`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com). You need it if you must render or apply the GitLab chart locally — typically only during an incident when CI is unavailable. Follow the setup instructions in that repository's [README](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/README.md).

All other platform workloads (Vault, Prometheus, Mimir, KEDA, cert-manager, and so on) are managed by [ArgoCD](https://argocd.gitlab.net/) via [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps). Local `helmfile` invocations are not the operational path for those.

## HAProxy state for zonal clusters

Draining a zonal cluster from HAProxy is destructive to that zone's traffic. Use only in extreme circumstances (for example, evacuating traffic before a rebuild). Server state is set through consul KV and applied by [gitlab-haproxy-agent](../frontend/agent.md) on every load balancer; from a console node, one key per backend row of the zone:

```sh
consul kv get -recurse gitlab-haproxy-agent/state/
for row in web/web-gke-us-east1-b main_web/web-gke-us-east1-b api/api-gke-us-east1-b main_api/api-gke-us-east1-b \
           https_git/git-https-gke-us-east1-b ssh/shell-gke-us-east1-b websockets/ws-gke-us-east1-b \
           ai_assisted/ai-assisted-gke-us-east1-b registry/registry-us-east1-b pages_http/pages-us-east1-b pages_https/pages-us-east1-b; do
  consul kv put gitlab-haproxy-agent/state/$row maint
done
```

Deleting the keys puts the servers back. The row names come from `haproxy.cfg`; `count by (backend, server) (haproxy_server_status{server=~".*us-east1-b.*"})` in Mimir lists them for a zone.

See [k8s-cluster-rebuild.md](k8s-cluster-rebuild.md) for the full HAProxy drain procedure used during cluster rebuilds.

## Troubleshooting

### `kubectl get nodes` fails with connection refused

Bastion SSH is not set up. Follow [bastions](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/bastions) and [yubikey](../uncategorized/yubikey.md), then re-run `glsh kube setup`.

### `kubectl` fails with an auth error

Refresh credentials: `gcloud auth login` then `glsh kube setup`.

### `glsh` is missing or out of date

Follow [running helper scripts from runbook](../../README.md#running-helper-scripts-from-runbook) in the top-level README.
