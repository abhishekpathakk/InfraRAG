# Running Post-deployment Migrations Manually through a Change Request

This is a process which can be used to execute [post-deployment migrations] for GitLab.com that have failed repeatedly when executed using the [PDM pipeline]. The reason for repeated failure is (usually) an inability to acquire the lock required for a PDM when user traffic is high.

Such PDMs should be executed manually through a [Change request] at the lowest traffic times, usually early on Monday morning in APAC.

> [!note]
> Manually running a failed migration via Change Request is the responsibility of the team that authored the migration, not the release manager. Release managers may assist in coordinating, but the authoring team should own execution end-to-end.

## Procedure

The PDM will be executed in a Rails console inside the Toolbox pod, in the main stage of the `gprd` environment. Before executing the PDM, it is essential to ensure that the Toolbox pod is protected from voluntary eviction _during_ PDM execution using a [Pod Disruption Budget] Kubernetes resource. This resource is only added temporarily and **must** be removed once the PDM execution is complete.

### 1. Prerequisites

> [!note]
> Before running a PDM manually, the PDM must be skipped using the `/chatops gitlab run migrations mark <PDM-timestamp>` command. This command can be executed only **once** the PDM has been deployed to production.

> [!warning]
> A [Change request] is required in order to perform the steps mentioned in this runbook. Link this runbook within the `Change steps` section of the change request issue.

You will need access to the main stage of `gprd` environment through `kubectl` to follow this runbook.

Follow the guide to get [Kubernetes API access] and authenticate with the GKE cluster using `kubectl`.

You will also need access to run `kubectl apply` in `gprd`.

### 2. Connect to the Regional cluster in `gprd`

Connect to the regional cluster in the `gprd` environment: `gke_gitlab-production_us-east1_gprd-gitlab-gke`

### 3. Prepare Pod Disruption Budget resource manifest

Add a PDB targeting the `gitlab-migrations-toolbox` Deployment:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: gitlab-migrations-toolbox-pdb
  namespace: gitlab
spec:
  maxUnavailable: 0
  selector:
    matchLabels:
      app: toolbox
```

Save this manifest as `/tmp/pdb.yaml`.

This manifest will work as-is. You can confirm that the `gitlab-migrations-toolbox` is the only Deployment targeted by this PDB by running this command locally:

```sh
$ kubectl get deploy --selector='app=toolbox' --no-headers --namespace gitlab
gitlab-migrations-toolbox   1/1   1     1     77d
```

### 4. Create Pod Disruption Budget

Apply the above manifest using `kubectl apply`:

```shell
# PDB manifest saved to /tmp/pdb.yaml

$ kubectl apply --dry-run='server' -f /tmp/pdb.yaml
poddisruptionbudget.policy/gitlab-migrations-toolbox-pdb created (server dry run)

$ kubectl apply -f /tmp/pdb.yaml
poddisruptionbudget.policy/gitlab-migrations-toolbox-pdb created
```

### 5. Start Rails Console

This is the process for opening a Rails console in the Toolbox pod:

```shell
$ kubectl exec -it deploy/gitlab-migrations-toolbox --container toolbox --namespace gitlab -- /bin/bash
git@gitlab-migrations-toolbox-58d74dbc76-6868v:/$ gitlab-rails console
--------------------------------------------------------------------------------
 Ruby:         ruby 3.2.8 (2025-03-26 revision 13f495dc2c) [x86_64-linux]
 GitLab:       18.5.0-rc43-ee (6ca6c213697) EE
 GitLab Shell: 14.45.3
 PostgreSQL:   16.9
------------------------------------------------------------[ booted in 36.25s ]
Loading production environment (Rails 7.1.5.2)
irb(main):001>

```

### 6. Run Post-Deployment Migration

Now that the PDB has been created, the Toolbox pod is protected from voluntary evictions.

> [!note]
> Replace the file name and migration class name with the migration that you want to execute.

Within the Rails console, run the following commands:

```ruby
require Rails.root.join('db/post_migrate/20250101001122_post_deployment_migration.rb')

PostDeploymentMigration.new.up
```

Once PDM execution is completed successfully, proceed to the next step.

A successful run outputs something like:

```ruby
== 20250101001122 PostDeploymentMigration: migrating ==============================
...
== 20250101001122 PostDeploymentMigration: migrated (X.XXXs) ================
```

If the migration raises an exception, **do not delete the PDB yet**. Escalate to the team
that authored the migration to investigate. Only delete the PDB once the situation is resolved.

### 7. Delete Pod Disruption Budget

The PDB resource will prevent the Toolbox pod from being evicted when we need it to be evicted for a legitimate reason (such as migration to a different node due to node autoscaling)

So, delete the PDB resource from the cluster:

```shell
$ kubectl delete -f /tmp/pdb.yaml
```

## References

- [Change request to run a PDM manually](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20640)

[PDM pipeline]: https://gitlab.com/gitlab-org/release/docs/-/blob/master/general/database-migrations/post-deploy-migration/readme.md
[Change request]: https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/#does-my-change-need-a-change-request
[Pod Disruption Budget]: https://kubernetes.io/docs/tasks/run-application/configure-pdb
[post-deployment migrations]: https://docs.gitlab.com/development/migration_style_guide/#choose-an-appropriate-migration-type
[Kubernetes API access]: ../kube/k8s-oncall-setup.md#kubernetes-api-access
