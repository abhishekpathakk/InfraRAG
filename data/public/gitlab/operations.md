# NATS Operations

For general operations it is recommended to rely on `helm` mechanisms to control and configure the NATS release. It is controlled via environment specific configurations like [here](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/nats/env/analytics-eventsdot-stg).

## Deploying changes via ArgoCD

NATS is deployed by an ArgoCD **ApplicationSet** defined in [`argocd/apps` under `services/nats`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/nats). Its `syncPolicy` has two independent settings:

* **`automated`:** when on, merged git changes sync to the cluster on their own, so a merged MR deploys promptly — treat any merge to NATS as an immediate deploy.
* **`selfHeal: false` (disabled):** Argo does not autonomously re-apply the manifest to correct live drift. This does not prevent merged changes from syncing; it just leaves out-of-band `kubectl patch` changes in place until the next sync.

Auto-sync can be toggled by merged changes, so don't assume a fixed state — check the current `syncPolicy` in [`services/nats/service.yaml`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/nats/service.yaml) or the application's **Sync Policy** panel in the [ArgoCD UI](https://argocd.gitlab.net).

> [!warning]
> A Sync — including a manual UI Sync — does a server-side apply of the full manifest and reverts anything not in it. This includes out-of-band `kubectl patch` changes and any manually-added annotations, e.g. a `reloader.stakater.com/auto=false` set during recovery to pause Reloader (annotations that *are* in the manifest are preserved — see [Config reloads](#config-reloads-stakater-reloader)). During a long recovery, do not Sync (or merge to a still-auto-syncing app) without confirming with the incident commander.

### Toggling auto-sync

Enable or disable auto-sync from the [ArgoCD UI](https://argocd.gitlab.net): on the application, open **App Details → Sync Policy** and use **Enable/Disable Auto-Sync**.

### Manually syncing

If auto-sync is disabled (or a merged change did not sync), trigger a sync from the [ArgoCD UI](https://argocd.gitlab.net) using the **Sync** button on the application, then verify it is `Synced` and `Healthy`.

### Config reloads (Stakater Reloader)

NATS ConfigMaps are watched by [Stakater Reloader](https://github.com/stakater/Reloader), which by default **rolling-restarts the NATS StatefulSet** on a ConfigMap change — so a config change is disruptive. Recovery pauses this by annotating the StatefulSet `reloader.stakater.com/auto=false`. Note that not all settings are hot-reloadable via SIGHUP (e.g. JetStream `max_file_store` needs a restart). Confirm the [authoritative config in `argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/nats) before assuming any config change applies without a restart.

## Scaling and storage

### Scaling replicas

Cluster replicas be increased by changing:

```diff
--- a/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
+++ b/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
@@ -11,7 +11,7 @@ config:
     enabled: true
     name: analytics-eventsdot-stg
     port: 6222
-    replicas: 3
+    replicas: 5

   jetstream:
     enabled: true

```

### Increasing Jetstream storage

Increasing the NATS Jetstream storage is not quite as simple as increasing the `size` in helm values. This is because how Kubernetes doesn't allow StatefulSets spec to be modified expect few selected fields.

```diff
--- a/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
+++ b/releases/nats/analytics-eventsdot-stg.yaml.gotmpl
@@ -22,7 +22,7 @@ config:

       pvc:
         enabled: true
-        size: 100Gi
+        size: 200Gi
```

So we need to following additional steps to actually sync the above helm state with the cluster.

1. List the PVCs first

    ```shell
    $ kubectl get pvc -l app.kubernetes.io/name=nats -n <namespace>
    ````

1. Patch each pvc individually with the increase to its storage size

    ```shell
    # This assumes 3 PVCs as per the above output, should be adjusted for actual count
    for i in 0 1 2; do
      kubectl patch pvc nats-js-nats-$i -n nats \
        --type merge -p '{"spec":{"resources":{"requests":{"storage":"3Ti"}}}}'
    done
    ```

1. Force a deletion of `nats` StatefulSet **without deleting the actual pods**

    ```shell
    kubectl delete statefulset nats -n nats --cascade=orphan
    ```

1. Sync helm changes with the cluster, which recreates the StatefulSet with the updated storage. Merging triggers the sync automatically (see [Deploying changes via ArgoCD](#deploying-changes-via-argocd)) — afterward **verify the application actually synced**, and trigger a [manual sync](#manually-syncing) if it did not.

[NATS cli](https://github.com/nats-io/natscli) is also available on the deployed environments via the `nats-box` deployment. During troubleshooting or incidents operational tasks like restart, configuration changes can be done in the `nats-box` container.

NATS administration [doc](https://docs.nats.io/running-a-nats-service/nats_admin) provide good reference on additional operational tasks.
