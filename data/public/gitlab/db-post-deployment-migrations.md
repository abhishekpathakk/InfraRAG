# Container Registry database post-deployment migrations

## Context

Until recently the registry only had support for regular database schema migrations. After completing the GitLab.com registry upgrade/migration ([gitlab-org&5523](https://gitlab.com/groups/gitlab-org/-/epics/5523)), we're now in a position where the database has grown enough to make simple changes (like creating new indexes) take a long time to execute, so we had to introduce support for post-deployment migrations.

Regular schema migrations are automatically applied by the registry helm chart using a migrations job, introduced in [gitlab-org/charts/gitlab#2566](https://gitlab.com/gitlab-org/charts/gitlab/-/issues/2566). The mid/long-term goal is to have a similar automation for post-deployment migrations ([gitlab-com/gl-infra/delivery#3926](https://gitlab.com/gitlab-com/gl-infra/delivery/-/issues/20909)).

Meanwhile, we're already feeling the need to ship post-deployment migrations, so we had to move forward with a short-term solution. This implies skipping any post-deployment migrations during deployments and then raising a change request to have these manually applied from within a registry instance after deploying a version that includes new post-deployment migrations.

This document provides instructions for SREs to apply post-deployment migrations.

## Applying post-deployment migrations

### Prerequisites

Before proceeding with the container registry post-deployment migrations, ensure the following prerequisites are met:

1. Check if there are pending post deployment migrations by looking at the panel titled "Pending PDMs" in the
   [registry database detail dashboard](https://dashboards.gitlab.net/d/registry-database/registry3a-database-detail?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-namespace=gitlab&var-Deployment=gitlab-registry&var-cluster=$__all&var-shard=default&viewPanel=panel-12).
   On the dashboard, select the environment you are interested in.

1. Confirm that there is only one registry version running in the target environment
   ([dashboard](https://dashboards.gitlab.net/d/registry-app/registry3a-application-detail?from=now-5m&orgId=1&to=now&viewPanel=panel-3&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-cluster=gprd-us-east1-b&var-stage=main&var-namespace=gitlab)).
   On the dashboard, select each zonal cluster of the environment and make sure they are all running the same registry
   version.

### CI pipeline

The pipeline to be executed is in <https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com>.
Open a CR and request an SRE to perform the following steps if you do not have access to the project.

1. Ping `@release-managers` on `#g_delivery` channel in Slack to find a good time to execute container registry
   post deployment migrations on pre, staging and production. Deployments to pre, staging and production will have to
   be paused while executing post deployment migrations.

1. Execute the `Execute container registry post deployment migrations` inactive pipeline schedule from
   <https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/pipeline_schedules>.

   Or you can start a pipeline using the following link, which will take you to the "Run new pipeline" page with the
   required variables pre-filled:
   [Create new pipeline](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/pipelines/new?var[REGISTRY_POST_DEPLOYMENT_MIGRATIONS]=true&var[DRY_RUN]=false)

The pipeline will execute container registry post deployment migrations on pre, staging and production, in that order.
After executing migrations in each environment, it will execute container registry QA on that environment. Any failure
in executing migrations, or in QA will prevent the pipeline from proceeding to the next environment.

The pipeline creates a Kubernetes job on the regional cluster of each environment to execute migrations.

#### Logs

Logs for the execution of container registry PDMs can be found in Kibana under the `pubsub-registry-inf-pre*`,
`pubsub-registry-inf-gstg*` and `pubsub-registry-inf-gprd*` data views. The
`json.pod_name: "registry-post-deploy-migrations"` attribute can be used to filter and show container registry
PDM logs.

The following links take you to saved searches with the data view selected and the filter prefilled. Adjust the time
range based on when the migrations were executed.

| Environment | Kibana link                                    |
| ----------- |------------------------------------------------|
| pre         | <https://nonprod-log.gitlab.net/app/r/s/Nlr26> |
| staging     | <https://nonprod-log.gitlab.net/app/r/s/f79al> |
| production  | <https://log.gprd.gitlab.net/app/r/s/rqumI>    |

#### Starting a pipeline to apply post deployment migrations on a particular environment

If you need to start a pipeline to execute container registry post deployment migrations on a particular environment
only, you can start a pipeline on <https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com> with the
following variables:

- `REGISTRY_POST_DEPLOYMENT_MIGRATIONS`: `true`
- `DRY_RUN`: `false`
- `ENVIRONMENT`: `pre` or `gstg` or `gprd`

The following link will take you to the "Run new pipeline" page with the variables pre-filled. Don't forget to change
the value of the `ENVIRONMENT` variable:
<https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/pipelines/new?var[REGISTRY_POST_DEPLOYMENT_MIGRATIONS]=true&var[DRY_RUN]=false&var[ENVIRONMENT]=pre>

### Manually executing post deployment migrations

> [!warning]
> The CI pipeline is the preferred method of executing post deployment migrations, but if it is required to manually
> execute post deployment migrations on an environment, the steps are listed below.

There's a private recording from delivery team for applying the migrations: [https://www.youtube.com/watch?v=QFH11OE91Vw](https://www.youtube.com/watch?v=QFH11OE91Vw)

This should be done from within a registry instance in K8s, using the built-in `registry` CLI. If needed, you can look at the relevant CLI documentation [here](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs-gitlab/database-migrations.md#administration).

1. Confirm that the registry version indicated in the Change Request matches the one (and there is only one) running in the target environment ([dashboard](https://dashboards.gitlab.net/d/registry-app/registry-application-detail?orgId=1&from=now-5m&to=now&viewPanel=3));

1. Connect to any cluster from the environment for which maintenance is occurring ([runbook](../kube/k8s-oncall-setup.md#kubernetes-api-access));

    **Note** that the regional clusters in `gprd` and `gstg` do not have any Registry pods. So, you can connect to any one of the three zonal clusters.

1. Find the oldest container registry Pod (ignore Pods that have `-migrations-` in the name!) and access it using `kubectl`:

   ```sh
   POD_NAME=$(kubectl get pods -n gitlab -l app=registry --sort-by=.metadata.creationTimestamp -o name | grep -v -- "-migrations-" | head -n 1) && \
       [ -n "$POD_NAME" ] && kubectl exec -n gitlab -it $POD_NAME -- /bin/bash || \
       echo "Pod name \"$POD_NAME\" is invalid."
   ```

   > [!note]
   > If you are running `kubectl exec` on a cluster in the `gprd` environment, then notify SIRT via `Slack -> SIRTBot -> Notify SecOps button` that you are exec-ing into the pod with a link to the change request, as they will receive a SIRT alert about it.

1. List pending migrations:

   ```sh
   SKIP_POST_DEPLOYMENT_MIGRATIONS=false registry database migrate status /etc/docker/registry/config.yml
   ```

   You should see something like this:

   ```text
   pre-deployment:
   +---------------------------------------------------------------------------------+--------------------------------------+
   |                                    MIGRATION                                    |               APPLIED                |
   +---------------------------------------------------------------------------------+--------------------------------------+
   | 20210503145024_create_top_level_namespaces_table                                | 2022-11-29 14:12:58.477128 +0000 WET |
   | 20220803114849_update_gc_track_deleted_layers_trigger                           | 2022-11-29 14:13:00.209522 +0000 WET |
   | ...                                                                             | ...                                  |
   +---------------------------------------------------------------------------------+--------------------------------------+

   post-deployment:
   +---------------------------------------------------------------------------------+--------------------------------------+
   |                                    MIGRATION                                    |               APPLIED                |
   +---------------------------------------------------------------------------------+--------------------------------------+
   | 20210503145024_post_add_layers_simplified_usage_index_batch_0                   | 2022-11-29 14:12:58.477128 +0000 WET |
   | 20220803114849_post_add_layers_simplified_usage_index_batch_1                   | 2022-11-29 14:13:00.209522 +0000 WET |
   | ...                                                                             | ...                                  |
   | 20221123174403_post_add_layers_simplified_usage_index_batch_2                   |                                      |
   +---------------------------------------------------------------------------------+--------------------------------------+

   ```

   In this example, there is one pending post-deployment migration named `20221123174403_post_add_layers_simplified_usage_index_batch_2`. You know it's a pending post-deploy migration because it is in the `post-deployment` table section and because `APPLIED` is empty.

   Note that we're explicitly disabling the `SKIP_POST_DEPLOYMENT_MIGRATIONS` environment variable for these commands. If we don't, then the registry CLI will ignore post-deployment migrations. This environment variable is set to `true` for our deployments ([sample](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/62be0606e27a2af17d91d3857e914dc08a631283/releases/gitlab/values/gprd-cny.yaml.gotmpl#L224)) to avoid having these migrations applied alongside regular schema migrations during upgrades.

1. Confirm that there are no pending regular migrations in the list above;

1. Confirm that the number and name of pending post-deployment migrations matches those described in the change request;

1. Suspend execution if any conditions above are not met. Contact the change request development DRI to evaluate results and determine how to proceed. Do not continue until explicit guidance is received from the DRI. cancel the change if no response is received within the operational window;

1. Proceed to apply post-deployment migrations:

   ```sh
   SKIP_POST_DEPLOYMENT_MIGRATIONS=false registry database migrate up /etc/docker/registry/config.yml
   ```

   You should see something like this:

   ```text
   post-deployment:
   20221123174403_post_add_layers_simplified_usage_index_batch_2
   OK: applied 0 pre-deployment migration(s), 1 post-deployment migration(s) and 0 background migration(s)
   ```

1. Wait for the above to complete and confirm there are no pending migrations:

   ```sh
   SKIP_POST_DEPLOYMENT_MIGRATIONS=false registry database migrate status /etc/docker/registry/config.yml
   ```

   You should see something like this:

   ```text
   pre-deployment:
   +---------------------------------------------------------------------------------+--------------------------------------+
   |                                    MIGRATION                                    |               APPLIED                |
   +---------------------------------------------------------------------------------+--------------------------------------+
   | 20210503145024_create_top_level_namespaces_table                                | 2022-11-29 14:12:58.477128 +0000 WET |
   | 20220803114849_update_gc_track_deleted_layers_trigger                           | 2022-11-29 14:13:00.209522 +0000 WET |
   | ...                                                                             | ...                                  |
   +---------------------------------------------------------------------------------+--------------------------------------+

   post-deployment:
   +---------------------------------------------------------------------------------+--------------------------------------+
   |                                    MIGRATION                                    |               APPLIED                |
   +---------------------------------------------------------------------------------+--------------------------------------+
   | 20210503145024_post_add_layers_simplified_usage_index_batch_0                   | 2022-11-29 14:12:58.477128 +0000 WET |
   | 20220803114849_post_add_layers_simplified_usage_index_batch_1                   | 2022-11-29 14:13:00.209522 +0000 WET |
   | ...                                                                             | ...                                  |
   | 20221123174403_post_add_layers_simplified_usage_index_batch_2                   | 2022-12-14 12:31:57.42551 +0000 WET  |
   +---------------------------------------------------------------------------------+--------------------------------------+

   ```

   Note that `APPLIED` in the `post-deployment` table is no longer empty.

## Monitoring

The migrations tool used by the registry ([link](https://pkg.go.dev/github.com/rubenv/sql-migrate)) does not report when each individual migration has been applied, only when all pending are done (or one fails). As result, when applying multiple migrations, the registry CLI will output the list of all migrations to apply and wait for all to be applied (or for one to fail) before providing additional feedback (success or failure).

While the tool does not support realtime feedback, if applying multiple long-running migrations and wanting to know the progress of each one, we can use the `registry database migrate status /etc/docker/registry/config.yml` CLI command on another registry pod to see the list of migrations already applied.

Alternatively, we can look directly at the `post_deploy_schema_migrations` table (from where the `database migrate status` reads post-deployment migrations) on the registry database with the following query:

```sql
SELECT * FROM post_deploy_schema_migrations ORDER BY applied_at DESC LIMIT 10;
```

The output will look like follows:

```text
                              id                               |          applied_at
---------------------------------------------------------------+-------------------------------
 20221123174403_post_add_layers_simplified_usage_index_batch_2 | 2022-12-21 19:02:19.923828+00
 20221123174403_post_add_layers_simplified_usage_index_batch_1 | 2022-12-21 19:02:19.923828+00
 20221123174403_post_add_layers_simplified_usage_index_batch_0 | 2022-12-21 19:02:19.923828+00
 ...                                                           | ...

(10 rows)
```

As each post-deployment migration is applied, it will be inserted in this table, with the current time set in `applied_at`. So we can glance at this query result when wondering how many post-deployment migration have been already applied.

Follow [this guide](../teleport/Connect_to_Database_Console_via_Teleport.md) on how to connect to the registry database using `tsh`.
