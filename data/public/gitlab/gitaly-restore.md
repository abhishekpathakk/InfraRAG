# Restore Gitaly data on `ops.gitlab.net`

Currently, Gitaly is a single point of failure in our `ops.gitlab.net` instance, in that it is a single persistent disk with no replication, failover or anything fancy like that. This is less than ideal since Ops is supposed to contain everything we need to get `gitlab.com` itself back up and running, should we ever need to.

To facilitate recovery of Gitaly data in the event of a disaster befalling `ops.gitlab.net`, we have set up a backup and restoration plan for it in [Backup for GKE](https://docs.cloud.google.com/kubernetes-engine/docs/add-on/backup-for-gke/concepts/backup-for-gke).

The backup and restoration plans are managed in [`config-mgmt` using Terraform](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/ops/gke-us-central1.tf#L169).

The scope of the backup only includes Gitaly, and not other components of the instance requiring persistent storage such as Redis. This is achieved by defining a [`ProtectedApplication`](https://docs.cloud.google.com/kubernetes-engine/docs/add-on/backup-for-gke/how-to/protected-application) object with a `matchLabels` selector for `app: gitaly`. This `ProtectedApplication` is deployed as part of the [`gitlab-ops` ArgoCD service](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/gitlab-ops/manifests/gitaly-protected-application.yaml). One thing to note is that the selector includes a lot more than just the `PersistentVolume` containing Gitaly data - it also pulls in things like `ServiceMonitors` which we don't need or want to restore as well, so we try to limit the restoration process to only the things we need to be restored.

## Procedure

1. If you haven't already, set your `kubectl` context to the `ops-central` GKE cluster and connect to it: `glsh kube use-cluster ops-central`
2. Check that the existing Gitaly PV has a `ReclaimPolicy` of `Retain`: `kubectl get pv <name-of-pvc> --namespace gitlab`
3. Scale down the Gitaly StatefulSet: `kubectl scale statefulsets ops-gitlab-gitaly --replicas=0 --namespace gitlab`
4. Delete the Gitaly PVC: `kubectl delete pvc repo-data-ops-gitlab-gitaly-0 --namespace gitlab`.
     - After this the status of the PV should be `Released`.
5. Run the restore plan. You can do this via the GCP console or using `gcloud` (note that the `gcloud` interface is under the beta component)
     - **In the GCP console**:
       - Click on the **Set up a restore** button next to the latest backup on the [backups page](https://console.cloud.google.com/kubernetes/backups/locations/us-west1/backupPlans/ops-gitaly-backup-plan/backups?project=gitlab-ops)
       - In the form:
         - For "Choose a restore plan" select `ops-gitaly-restore-plan`
         - For "Name the restore" enter `cr-18439-test-restore`
         - Expand "Show advanced options" and tick "Enable fine-grained restore"
         - Under "Inclusion filters" click "Add Filter Condition"
         - In the sidebar form, enter `PersistentVolumeClaim` in "Object kind" and leave the other fields blank
         - Save changes and hit the Restore button
     - **Using `gcloud`**:
       - Create and save a filter file `filter.yaml` with the following content in your working directory:

          ```yaml
           inclusionFilters:
            - groupKind:
                resourceKind: PersistentVolumeClaim
          ```

       - Get the name of the backup you want to restore on [this page](https://console.cloud.google.com/kubernetes/backups/locations/us-west1/backupPlans/ops-gitaly-backup-plan/backups?project=gitlab-ops). If in doubt just use the latest one.
       - Run the following command: `gcloud beta container backup-restore restores create ops-gitaly-restore --project=gitlab-ops --location=us-west1 --restore-plan=ops-gitaly-restore-plan --backup=<name-of-backup> --filter-file=filter.yaml`
6. A new PVC `repo-data-ops-gitlab-gitaly-0` should have been created.
    - If its status is stuck at `waiting for first consumer to be created before binding`, this is expected!
7. Scale the Gitaly STS back to 1: `kubectl scale statefulsets ops-gitlab-gitaly --replicas=1 --namespace gitlab`
8. After a few minutes, that the restored PV is now claimed by the PVC: `kubectl get pvc repo-data-ops-gitlab-gitaly-0 --namespace gitlab`

After restoration, it might be a good idea to check that all Git operations work as expected.
