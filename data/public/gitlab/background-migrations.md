# Container Registry Batched Background Migrations

## Background

The Container Registry (on GitLab.com) supports background migrations. This feature is implemented as described in the [technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-background-migrations.md).

For now, this feature is disabled on both Staging and Production. You can follow [Container Registry: Batched Background Migration (BBM) (&15336)](https://gitlab.com/groups/gitlab-org/-/epics/15336) for more updates. The rollout plan being followed is detailed [here](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-background-migrations.md#release-plan-phases).

## Issues

Issues related to background migrations are reported to the [container registry's team alerts channel on slack](https://gitlab.enterprise.slack.com/archives/C046REGL9QD) via Sentry.

## Logs

To find all relevant log entries, you can filter logs in Kibana by `json.component: registry.bbm.Worker` ([example](https://nonprod-log.gitlab.net/app/r/s/oQUxS)).

## Metrics

There are graphs for all relevant database metrics in the [registry: Database Detail](https://dashboards.gitlab.net/goto/ulhoLB7NR?orgId=1) dashboard.

## Managing Background Migrations on GitLab.com

To manage and administer background migrations from the [command line](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-background-migrations.md#cli), follow these steps:

Prerequisites:

- Access to the Registry pods: You need access to the GitLab Registry pods for executing CLI commands.
- Access to the PostgreSQL database: For advanced management tasks, you may also need direct access to the PostgreSQL database.

Steps to Manage Background Migrations:

1. Connect to a Registry Pod. For example, if a registry pod is named `gitlab-registry-5ddcd9f486-bvb57`, use the following command:

    ```shell
    kubectl exec -ti gitlab-registry-5ddcd9f486-bvb57 bash
    ```

1. Once inside the pod, you can run various registry commands to start, pause, or view the status of background migrations. These commands are outlined in the [CLI section](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-background-migrations.md#cli). For example, to pause all background migrations, use:

    ```shell
    /usr/bin/registry background-migrate pause /etc/docker/registry/config.yml
    ```

**Note**: Once a background migration is active, it is not recommended to directly modify or change the `background_migration_jobs` table in PostgreSQL. Making manual changes to this table could cause corruption or interfere with the migration process. However, PostgreSQL administrators can still interact with the migration records safely, such as pausing or starting migrations on the `background_migration` table, provided these actions are performed carefully.

For administrators with access to the PostgreSQL database, you can pause, start, or view specific migrations directly from the database.

- Pause a Specific Migration:

    ```sql
    UPDATE batched_background_migrations
    SET status = 0 -- 'paused'
    WHERE name = '<migration_name>';
    ```

- Start a Specific Migration:

    ```sql
    UPDATE batched_background_migrations
    SET status = 1 -- 'active'
    WHERE name = '<migration_name>';
    ```

- View a Specific Migration:

    ```sql
    SELECT name, status, started_at, finished_at
    FROM batched_background_migrations
    WHERE name = '<migration_name>';
    ```

## Related Links

- [Feature epic](https://gitlab.com/groups/gitlab-org/-/epics/13609)
- [Technical specification](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/spec/gitlab/database-background-migrations.md)
