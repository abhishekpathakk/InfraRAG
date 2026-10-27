# Isolate a pod

Isolate a pod for troubleshooting, profiling, or inspection without disrupting the running workload. Removing a label that matches the Deployment's `spec.selector.matchLabels` de-associates the pod from the Deployment — Kubernetes then schedules a fresh replacement, leaving the isolated pod running with its original state.

Useful for:

- Reproducing a bug on a specific pod while a fix rolls out on the rest of the Deployment.
- Grabbing a live process for `perf`, `strace`, or heap dumps.
- Keeping a "before" pod around during an upgrade for comparison.

## Procedure

Find the Deployment's selector labels:

```sh
kubectl describe deploy --namespace=gitlab <deployment>
```

Look under `Selector` / `spec.selector.matchLabels`.

Edit the pod and drop or rename one of the matching labels:

```sh
kubectl edit pod --namespace=gitlab <pod>
```

For example, if `matchLabels.component: app` is the selector, change it to `component-orig: app`. The pod remains running; Kubernetes creates a replacement pod to satisfy the Deployment's `replicas` count.

Confirm a new pod was scheduled:

```sh
kubectl get pods --namespace=gitlab --watch
```

The isolated pod may still receive Service traffic depending on the Service's selectors. To fully detach it from Service load-balancing, also drop labels that match the Service's `spec.selector`.

## Cleanup

The isolated pod is not managed by the Deployment — it will not be replaced if it dies, and it will not roll out on the next deploy. Delete it when you are done:

```sh
kubectl delete pod --namespace=gitlab <pod>
```

## Related

- [Kubernetes labels and selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)
- [Debug Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [k8s-operations.md — Attach to a running container](k8s-operations.md#attach-to-a-running-container)
