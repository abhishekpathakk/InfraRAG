# Cloud SQL Troubleshooting

Some services such as Praefect, `ops.gitlab.net` or Grafana use a Google Cloud
SQL PostgreSQL instance.

On occasion it will be necessary to connect to it interactively in a `psql`
shell. As with all manual database access, this should be kept to a minimum,
and frequently-requested information should be exposed as Prometheus metrics if
possible.

## General case

### Logs

The Cloud SQL logs can be accessed in the
[Operations console](https://cloudlogging.app.goo.gl/uJN6NWcjtK8mwaN89).

### Query Insights

The [Query Insights](https://docs.cloud.google.com/sql/docs/postgres/using-query-insights)
dashboard can be used to detect and analyze performance problems. To use it,
either go to the *Query Insights* tab of the Cloud SQL instance in the GCP
console, or
[enable it via Terraform](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance#query_insights_enabled).

## Connecting to the Cloud SQL database

1. Retrieve the user and password for the database from the application configuration (GKMS for Chef, Terraform state, other...)
2. Find the instance you are targetting:

   ```
   gcloud --project gitlab-production sql instances list
   ```

3. Connect to the instance using `gcloud` (paste in the password when prompted):

   ```
   gcloud --project gitlab-production sql connect <instance> -u <user>
   ```

## Alternative connection method via kubernetes

This example works for the `ops-central` instance:

1. Connect to the ops-central cluster
   `glsh kube use-cluster ops-central`
1. Get the password for the instance:
   `kubectl -n gitlab get secret postgres-credentials-v1 -o jsonpath='{.data.password}' | base64 -d`
1. Access the instance using the toolbox, using the password from the previous command
   `kubectl -n gitlab exec -ti <toolbox-pod> -c toolbox -- psql -h 127.0.0.1 -p 5432 -U gitlab -W gitlabhq_production`

## Gaining immediate access to a CloudSQL Instances

This section will show one way of gaining initial access to a CloudSQL Instance quickly. It is especially useful if you are asked to take over support for an instance which has not had other access methods setup and where you know you will need cloudsqlsuperuser access.
This is based on [Using the client in the Cloud Shell Google Documentation](https://docs.cloud.google.com/sql/docs/postgres/connect-admin-ip#cloud-shell) which should be read. I'm adding extra notes relevant to Gitlab.

A quick and easy way to connect to psql on a CloudSQL instance (aka without any other setup) is via gcli in the browser. This only works for CloudSQL instances with public ips, and without encryption turned on. Because we don't want our instances to have encryption turned off and we don't want our instances to have public ips, we probably don't actually want to use this method to connect to CloudSQL instances long term. This is about gaining initial access.

The basic command is `gcloud sql connect {instance_name} --user={user_name} --database={database_name}` run in gcli.

If a user already exists with adequate permissions and credentials you know, you can use those credentials.

If you have to make a user, make a builtin user and then put its credentials in the Production repo of 1Password in the format `{gcp project} {instance name} {username}` for example `gitlab-subscriptions-staging customers-db-4dc5 dbo_team`.

A new builtin user will automatically receive cloudsqlsuperuser permissions (as discussed in the section Understanding difference in initial roles granted between Cloud_IAM and BuiltIn Users for CloudSQL below)

Then longer term it is better to use private ips, encryption and Cloud_IAM users for access to CloudSQL instances.

## What permissions are needed to support a CloudSQL Instance

If you are asked to support a CloudSQL instance you will need to following access in order to do an adequate job.

1. Access to a Postgres User with cloudsqlsuperuser role. This can be a Builtin user or a Cloud_IAM user (but read the section Understanding difference in initial roles granted between Cloud_IAM and BuiltIn Users for CloudSQL below to understand which one to setup first if you have no other access to the instance) The cloudsqlsuperuser role allows you to connect to the database as basically a sysadmin - or as close to a sysadmin as GCP will allow a CloudSQL instance user to be.
2. GCP IAM Role role/cloudsql.admin on the CloudSQL Instance. I assign the role to the entire DBO_team to avoid the lottery problem, and usually for the entire project unless there is a good reason why you would want access on only some of the CloudSQL Instances in a project and not others.

```
resource "google_project_iam_member" "dbo_cloudsql_admin_user" {
  project = var.project
  role    = "roles/cloudsql.admin"
  member  = "group:dbo@gitlab.com"
}
```

This permission allows you to perform necessary actions via gcli or the console. This will occasionally be necessary for maintenance even though Terraform is still the preferred way of making changes.
3. roles/storage.objectCreator and roles/storage.objectViewer on a GCP Bucket. The CloudSQL instances service account also has to have roles/storage.objectCreator and roles/storage.objectViewer on the same bucket. This bucket will be used for CloudSQL Imports/Exports, which are occasionally necessary for testing, maintenance, data transfer and DR.

# Major Version Upgrade In Place

This is based on the [Upgrade the database major version in-place Google Documentation](https://docs.cloud.google.com/sql/docs/postgres/upgrade-major-db-version-inplace) which should be read. I'm adding extra notes relevant to Gitlab.

## Rough Upgrade Process

1. Put the Databases in Maintenance Mode - this will depend on the application which is connected to the database. The database will have downtime during a major version upgrade in-place.
   1. For example, follow [these instructions](https://docs.gitlab.com/administration/maintenance_mode/#enable-maintenance-mode) to put a GitLab instance in Maintenance Mode.
2. Update the Postgres Major Version in Terraform by changing the database_version, then run atlantis plan and apply.
   1. The upgrade process takes approx 10min for an empty CloudSQL instance, and approx 20min for an instance with 60GB in use.
   1. It is likely the atlantis apply will time out but the process will continue and can be followed in the GCP Console or Logging Explorer.

> [!caution]
> Databases with replicas cannot be upgraded via Terraform and need to be upgraded manually via the GCP console. Once upgraded, you will need to update the Terraform and run an `atlantis plan -- -refresh` to ensure consistency of state.
>
> GCP's upgrade procedure requires the replication be stopped during the upgrade. Terraform is not capable of performing this ahead of time.

3. Run `ANALYZE;` on the newly upgraded CloudSQL instance. You will need to connect to each database in turn and run ANALYZE; on each one. If a database is empty and unused, there is no need to run ANALYZE on that database. I recommend having a builtin DBO_Team user on each CloudSQL Instance with cloudsqlsuperuser permissions on each CloudSQL Instance - you can use this user to connect and run ANALYZE via the gcli as well as other essential maintenance.
    - Connect via gcli (or any other method) `gcloud sql connect {instance_name} --user=dbo_team --database={database_name}`
      - If CLI access isn't an option, the SQL console in the web UI also works; but:
        - The console enforces a 5 minute timeout (`statement_timeout` is still needed for the backend)
        - No output is returned - `VERBOSE` does nothing.
    - Run analyze: This takes approx 0m for an empty database and approx 2min for an instance using 60GB of storage.

      ```SQL
      SET statement_timeout = 0;
      ANALYZE (VERBOSE);
      ```

    - Check it ran correctly:

      ```SQL
      SELECT schemaname, relname AS table_name, last_analyze, last_autoanalyze
      FROM pg_stat_all_tables
      ORDER BY last_analyze desc nulls first;
      ```

4. Here is your last chance to rollback, so if there are any quick tests you want to do this is the time.
5. Do whatever needs to be done to take the Database out of maintenance mode. Your downtime has ended.

## Special Considerations for a Major Version Upgrade from Postgres =< 12 to Postgres => 16

The CloudSQL docs say ["If you're using PostgreSQL versions 9.6, 10, 11, or 12, then version 3.4.0 of the PostGIS extension isn't supported. Therefore, to perform an in-place major version upgrade to PostgreSQL 16 and later, you must first upgrade to an intermediate version of PostgreSQL (versions 13, 14, or 15)."](https://docs.cloud.google.com/sql/docs/postgres/upgrade-major-db-version-inplace#:~:text=If%20you%27re%20using%20PostgreSQL%20versions%209.6%2C%2010%2C%2011%2C%20or%2012%2C%20then%20version%203.4.0%20of%20the%20PostGIS%20extension%20isn%27t%20supported.%20Therefore%2C%20to%20perform%20an%20in%2Dplace%20major%20version%20upgrade%20to%20PostgreSQL%2016%20and%20later%2C%20you%20must%20first%20upgrade%20to%20an%20intermediate%20version%20of%20PostgreSQL%20(versions%2013%2C%2014%2C%20or%2015))

This information appears to be inaccurate. PostGIS is already on 3.4.3 in multiple CloudSQL instances of ours running Postgres 12. Any new CloudSQL instance created on Postgres 12 also has PostGIS on 3.4.3. Experimentation shows that upgrading directly from Postgres 12 to Postgres 16 works perfectly.

I recommend checking any Postgres 12 instance has PostGIS minimum 3.4.0 before upgrading it to Postgres 16, and I recommend testing any upgrade process on a non-production instance before upgrading production. Aside from that, I think it is safe to go ahead and do major version upgrades from Postgres 12 to Postgres 16

We have let Google know about the potential inaccuracy in their documentation and they are looking into it.

## Rolling Back a Major Version Upgrade in Place

This is based on the [Upgrade the database major version in-place Google Documentation](https://docs.cloud.google.com/sql/docs/postgres/upgrade-major-db-version-inplace) which should be read. I'm adding extra notes relevant to Gitlab.

You are going to rollback to a point in time immediately prior to the major version upgrade, so if there have been any data changes since then they will be lost. For this reason I recommend rollback should only be done if the database is still in maintenance mode.

### Rough Rollback Process

1. Create a new CloudSQL Instance at the previous version. Takes approx 15min to spin up an empty CloudSql instance
2. Restore your pre-upgrade backup to the new instance. Should take around 0min for an empty instance, or approx 12min for an instance with 60GB data.
    i. Go to CloudSQL backups on each instance you want to rollback
    ii. Find the backup marked Pre-upgrade backup, POSTGRES_X to POSTGRES_Y.
    iii. Click ‘Restore’. Select ‘Overwrite existing instance’ and select an instance you created earlier
    iv. Click ’Restore’
3. Do whatever needs to be done to connect the Application to the new instance - this will depend on the application which is connected to the database.
4. Do whatever needs to be done to take the Database out of maintenance mode. Your downtime has ended.

# Understanding difference in initial roles granted between Cloud_IAM and BuiltIn Users for CloudSQL

I am documenting this here specifically because it is not documented in Google documentation, and because it is a confusion many people run into when they start working with CloudSQL. It is an extension of the [About PostgreSQL Users and Roles Google Documentation](https://docs.cloud.google.com/sql/docs/postgres/users)

Creating a new CLOUD_IAM user on a CloudSQL instance creates that user with the very low level cloudsqliamserviceaccount postgres role. But creating a new BUILT_IN user on a CloudSQL Instance creates that user with the role cloudsqlsuperuser which is the highest possible permissions on a CloudSQL instance.

Since you need access to the database in order to give a new CLOUD_IAM user more appropriate roles, this sets up a kind gross system where you first create your IAM users via TF, then log in with your BUILT_IN superuser to assign an appropriate role to your new CLOUD_IAM user

At the moment there is no way to add Postgres roles to a CLOUD_IAM user via Terraform for Google Cloud SQL.

However, the capacity to [add Postgres roles to a CLOUD_IAM user via Terraform does exist for AlloyDB](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/alloydb_user#database_roles-1:~:text=resource%20%22google_alloydb_user%22%20%22user2%22%20%7B). Also, [the JSON documentation for CloudSQL](https://docs.cloud.google.com/sql/docs/postgres/admin-api/rest/v1beta4/users#SqlServerUserDetails) does include the ability to pass SqlServerUserDetails.serverRoles[] so I imagine it is just the [terraform resource google_sql_user](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_user) that needs to be updated. Google has indicated in the future (perhaps Q3 2025) we will be able to add Postgres roles to a CLOUD_IAM user via Terraform for Google Cloud SQL.

# Understanding CloudSQL backups

It is important to understand there are essentially two major kinds of CloudSQL backups. I don't feel their pros and cons are well documented so I have writting down my understanding of the two here.

## Backups - equivalent to an instance wide snapshot of the whole CloudSQL instance

### Strengths

- Can be restored onto existing target instance, existing source instance or have a new target instance created from them
- Supports point in time restore
- Easily automated, configurable via terraform, gcli or console.
- Negligible performance impact to take or restore
- As little as 12 mins to restore 60GB instance
- Restore also includes restore of credentials and other settings

### Weaknesses

- Cannot be moved to a GCP Bucket, and cannot be moved or restored to another region, project, database as a service nor cloud provider.
- Always overwrites target instance completely, no option for partial restore
- Always taken on entire source instance, no option for a partial backup.

## Import/Export - equivalent to a pg_dump of a single Database

### Strengths

- Can be placed in a Google Cloud Bucket, after which they can be retention locked, or moved to another region, project, database as a service and/or cloud provider.
- Can export just one database on a source instance
- Not deleted when the source instance is deleted
- Can import database to target instance without overwriting existing databases on target instance

### Weaknesses

- Performance impact while being exported unless offloaded to a secondary instance
- Performance impact while being imported - unavoidable as far as I am aware
- Can only be imported if all the users in the database already exist on the target instance [link]
- Can only be imported if the cloudsqlsuperuser is granted the role which owned the source database [link]
- Up to 20min to export a 20GB database when offloaded to a secondary instance
- Up to 45min to import a 60GB database
- No native way to automate regular export/import - however you can always roll your own automation here.
- Does not support point in time import or restore
- Import does not include credentials and other instance wide settings.
It may also be possible to connect to a single database and run pg_dump yourself, which will give many more options for flags, filters, parameters etc. However this option was not tested while writing this document.
