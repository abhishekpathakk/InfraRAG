# Diagnose Before Delete: Single-Pod 5xx Incidents

## When to use this runbook

Use this runbook when dashboards or logs show that elevated 5xx errors are
isolated to a **single pod** (e.g. one Puma worker in the `web` or `api`
fleet). The instinct is to delete the pod or trigger a redeploy — that clears
the alert but destroys the evidence needed to find root cause. Follow the steps
below to capture diagnostics first, then remove the pod.

## Steps

### 1. Identify the pod

Confirm that the 5xxs are coming from a single pod and not spread across the
fleet. Check per-pod error rates in the web service dashboard and in logs.

- **Dashboards**: [web service overview](https://dashboards.gitlab.net/d/web-main/web-overview?orgId=1) — check the per-pod error rate panels to confirm the spike is isolated to a single pod.
- **Kibana**: filter `json.hostname: <pod-name>` and `json.status: [500 TO 599]` in the `pubsub-rails-inf-gprd-*` index. See [INC-7175](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21226) for an example.
  - [Logs by pod](https://log.gprd.gitlab.net/app/r/s/9qQSY)
  - [Error breakdown by host](https://log.gprd.gitlab.net/app/r/s/49tHE)
  - [Full backtrace view](https://log.gprd.gitlab.net/app/r/s/q98Os)
- **Sentry**: group errors by `server_name` to confirm the dominant error class is concentrated on one host.

Once you have the pod name, proceed immediately — do **not** delete it yet.

### 2. Isolate the pod

Remove the pod from the load-balancer rotation so it stops receiving new
traffic, but keep it running for inspection.

Follow **[docs/kube/k8s-isolate-pod.md](../kube/k8s-isolate-pod.md)**.

> **Do NOT delete the pod yet.** Deletion destroys all in-process state,
> logs, and memory that you need for diagnosis.

### 3. Capture diagnostics

Run the following while the pod is isolated and still alive.

#### a. Recent application logs

Pull the last few hundred lines from the pod:

```shell
kubectl -n gitlab logs <pod-name> --tail=500

# If the container has restarted, fetch logs from the previous instance:
kubectl -n gitlab logs <pod-name> --previous --tail=500
```

For a multi-container pod (e.g. with a sidecar), specify the container:

```shell
kubectl -n gitlab logs <pod-name> -c <container-name> --tail=500
```

Cross-reference with Kibana using `json.hostname: <pod-name>` for the full
structured log stream.

#### b. Stack trace / exception sample

In Sentry, filter by `server_name:<pod-name>` and note:

- The dominant exception class (e.g. `ArgumentError`)
- The full backtrace of the most recent occurrence
- The request path and parameters if available

Copy the Sentry event URL into the incident issue.

#### c. Ruby process snapshot / CPU flamegraph

See **[docs/uncategorized/ruby-profiling.md](../uncategorized/ruby-profiling.md)**
for the full procedure (stackprof, flamegraphs via `perf`).

Quick path using the GKE helper script (run on the GKE node — use `toolbox` on COS nodes since `perf` is not available in the default COS environment):

```shell
scripts/gke/perf_flamegraph_for_pod_id.sh <pod-name>
```

Save the resulting SVG and attach it to the incident issue.

#### d. Pod environment data

```shell
# Full pod description: image SHA, node, restart count, events
kubectl -n gitlab describe pod <pod-name>

# Node the pod is running on
kubectl -n gitlab get pod <pod-name> -o jsonpath='{.spec.nodeName}'

# Image digest
kubectl -n gitlab get pod <pod-name> \
  -o jsonpath='{.status.containerStatuses[*].imageID}'
```

Note the restart count and any recent `Warning` events in the `describe`
output — these often reveal OOM kills or liveness probe failures that preceded
the 5xx spike.

#### e. Network capture (optional)

If a network-level issue is suspected (e.g. upstream timeouts, TLS errors),
capture traffic on the pod's network namespace or interface:

```shell
# Using pod network namespace
scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh <pod-name>

# Using pod network interface
scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh <pod-name>
```

See also `scripts/gke/container_inspection_library.sh` for lower-level
container inspection helpers.

### 4. Preserve evidence

Before removing the pod, attach all captured artifacts to the incident issue:

- `kubectl logs` output (paste or attach as a file)
- `kubectl describe pod` output
- Flamegraph SVG (if generated)
- pcap file (if a network capture was taken)
- Sentry event URL(s)
- Image SHA / digest

### 5. Remove the pod

Once diagnostics are captured, delete the pod to restore normal capacity:

```shell
kubectl -n gitlab delete pod <pod-name>
```

The deployment controller will schedule a replacement automatically. Verify
the new pod comes up healthy and that the 5xx rate returns to baseline.

### 6. Follow up

If root cause is not yet identified:

1. Open an issue against the responsible service team with the captured
   diagnostics attached.
2. Reference the originating incident in the issue.
3. Link the new issue from the incident timeline.

## Related runbooks

- [docs/kube/k8s-isolate-pod.md](../kube/k8s-isolate-pod.md) — isolate a pod without deleting it
- [docs/kube/kubernetes.md](../kube/kubernetes.md) — general Kubernetes ops, pod restart inspection
- [docs/uncategorized/ruby-profiling.md](../uncategorized/ruby-profiling.md) — Ruby profiling on k8s pods (stackprof, flamegraphs)
- [scripts/gke/perf_flamegraph_for_pod_id.sh](../../scripts/gke/perf_flamegraph_for_pod_id.sh) — CPU flamegraph for a pod
- [scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh](../../scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh) — network capture via pod netns
- [scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh](../../scripts/gke/tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh) — network capture via pod interface
- [scripts/gke/container_inspection_library.sh](../../scripts/gke/container_inspection_library.sh) — container inspection helpers
