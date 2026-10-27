# Teleport Disaster Recovery

## Backup and Restore

The backup practice is based on the official Teleport
[guide](https://goteleport.com/docs/admin-guides/management/operations/backup-restore/#our-recommended-backup-practice).
For more details on how we made decisions and implemented back and restore process, please see this
[epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/1357).

- Teleport Agents and [Proxy](https://goteleport.com/docs/reference/architecture/proxy/) Service are stateless.
- We use the *Google Cloud Key Management Service* (KMS) to store and handle Teleport certificate authorities.
- We use [Firestore](https://cloud.google.com/firestore) as the [storage backend](https://goteleport.com/docs/reference/backends/)
    for Teleport and it is shared among all *Auth Service* instances.
- We also store the [session recordings](https://goteleport.com/docs/reference/architecture/session-recording/)
    on an [Object Storage](https://cloud.google.com/storage) bucket.
- The configurations, including the `teleport.yaml` files, are version controlled in our repositories and deloyed through CI.

As a result, we only need to backup the Firestore database used by Teleport both for persisting the state of Cluster and the audit logs.

### KMS

We do not manage any certificate authority and private keys inside the cluster. They are all stored in and managed by KMS.

> To help guard against data corruption and to verify that data can be decrypted successfully,
> Cloud KMS periodically scans and backs up all key material and metadata.
> At regular intervals, the independent backup system backs up the entire datastore to both online and archival storage.
> This backup allows Cloud KMS to achieve its durability goals.

Please refer to this [deep dive document](https://docs.cloud.google.com/docs/security/key-management-deep-dive#datastore-protection)
on Google Cloud KMS and automatic backups.

### Firestore

The `(default)` Firestore database used by the Teleport cluster is backed up
[daily](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/7cfb8a1cd38bc16c01c0fb0f436e9297357c2867/modules/teleport-project/firestore.tf#L29). These daily backups have a retention period of `30` days for Teleport staging cluster and `90` days for Teleport production cluster.

To list the current backup schedules, run the following command:

```bash
$ gcloud firestore backups schedules list --project="gitlab-teleport-production" --database="(default)"
$ gcloud firestore backups schedules list --project="gitlab-teleport-staging" --database="(default)"
```

To list the current backups, run the following command:

```bash
$ gcloud firestore backups list --project="gitlab-teleport-production"
$ gcloud firestore backups list --project="gitlab-teleport-staging"
```

### Object Storage

The `gl-teleport-staging-teleport-sessions` and `gl-teleport-production-teleport-sessions` buckets
are used for storing the [session recordings](https://goteleport.com/docs/reference/architecture/session-recording/).

These buckets use the [Multi-Regional](https://docs.cloud.google.com/storage/docs/locations#location-mr) location
and have [soft deletion](https://docs.cloud.google.com/storage/docs/soft-delete)
and [versioning](https://docs.cloud.google.com/storage/docs/object-versioning) enabled.

Objects that have been in the bucket for 30 days will be automatically transitioned to the
[Nearline](https://docs.cloud.google.com/storage/docs/storage-classes#nearline) storage class
(see [this](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/5264ff990704be24398216378c17aff1312de735/modules/teleport-project/storage.tf#L14)).
Noncurrent objects (previous versions of objects) that have been noncurrent for 30 days will be automatically deleted
(see [this](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/5264ff990704be24398216378c17aff1312de735/modules/teleport-project/storage.tf#L24)).

The combination of multi-region storage, versioning, and soft deletion provide high **redundancy** and protect against loss of objects (files).

#### Restore a Backup

To restore a backup, run the following command:

```bash
$ gcloud firestore databases restore \
    --project="gitlab-teleport-production" \
    --destination-database="(default)" \
    --source-backup="projects/PROJECT_ID/locations/LOCATION/backups/BACKUP_ID" \

$ gcloud firestore databases restore \
    --project="gitlab-teleport-staging" \
    --destination-database="(default)" \
    --source-backup="projects/PROJECT_ID/locations/LOCATION/backups/BACKUP_ID" \
```

This is an asynchronous operation and it returns the *operation* created for restoring.
You can list the operations for a given Firestore database or describe a specific operation as follows.

```bash
$ gcloud firestore operations list --project="gitlab-teleport-production" --database="DATABASE"
$ gcloud firestore operations list --project="gitlab-teleport-staging" --database="DATABASE"

$ gcloud firestore operations describe --project="gitlab-teleport-production" "projects/PROJECT_ID/databases/DATABASE/operations/OPERATION_ID"
$ gcloud firestore operations describe --project="gitlab-teleport-staging" "projects/PROJECT_ID/databases/DATABASE/operations/OPERATION_ID"
```

For more details on how to backup and restore Firestore database,
please see the official [documentation](https://firebase.google.com/docs/firestore/backups).

## Automated Testing of Backups

We automatically verify our daily Firestore backups by running a daily job
that restores the latest backup to a new database and checks if the restoration was successful.
This process is implemented using Google [Cloud Functions](https://docs.cloud.google.com/functions/docs/concepts/overview)
and managed as infrastructure-as-code in the
[teleport-backup](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/modules/teleport-backup) Terraform module.

### Restore

The Firestore backup restoration function, implemented in [JavaScript](https://nodejs.org), is available
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/teleport-backup/functions/firestore-restore/index.js).
It follows a straightforward logic:
it retrieves the list of backups for the (default) database,
selects the latest one based on a timestamp field,
and creates an operation to restore it into a new database.
The new database's name starts with `restore-test-`, followed by the execution ID and backup UUID.

#### Schedule

The restore function is scheduled to run daily at `6:00` AM Eastern Time (UTC-05:00).
The schedule is defined using a [Cron](https://crontab.guru) pattern
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/077c5ad2d2ebb2e7a217e965bb30da506bbb5907/modules/teleport-backup/restore.tf#L63).

#### Monitoring

You can access this function in the Google Cloud Console at the following locations.

- [firestore-restore-v2 (production)](https://console.cloud.google.com/functions/details/us-central1/firestore-restore-v2?env=gen2&project=gitlab-teleport-production)
- [firestore-restore-v2 (staging)](https://console.cloud.google.com/functions/details/us-central1/firestore-restore-v2?env=gen2&project=gitlab-teleport-staging)

##### Logs

You can view the execution logs in the *LOGS* section of the pages mentioned above.
Each run has a unique execution ID that is prepended to each log message.

### Verify

The Firestore backup verification function, implemented in [JavaScript](https://nodejs.org), can be found
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/teleport-backup/functions/firestore-verify/index.js).
It has a straightforward logic: it retrieves the list of all Firestore databases in the Teleport project,
filters out those with names starting with the restore-test- prefix, and iterates through the list of operations for each database.
If any operation has failed, it logs and notifies the failure.
Finally, it cleans up the test databases created for restoration.

#### Schedule

The verify function is scheduled to run daily at `10:00` AM Eastern Time (UTC-05:00), which is four hours after the restore function.
The restoration operations are expected to be completed within this timeframe.
The schedule is defined using a [Cron](https://crontab.guru) pattern
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/077c5ad2d2ebb2e7a217e965bb30da506bbb5907/modules/teleport-backup/verify.tf#L77).

#### Monitoring

You can access this function in the Google Cloud Console at the following locations.

- [firestore-verify-v2 (production)](https://console.cloud.google.com/functions/details/us-central1/firestore-verify-v2?env=gen2&project=gitlab-teleport-production)
- [firestore-verify-v2 (staging)](https://console.cloud.google.com/functions/details/us-central1/firestore-verify-v2?env=gen2&project=gitlab-teleport-staging)

##### Logs

You can view the execution logs in the *LOGS* section of the pages mentioned above.
Each run has a unique execution ID that is prepended to each log message.

If a restoration fails, you'll see a log message with `ERROR` severity,
starting with a ❌ symbol and providing more details about the failure.

##### Metrics

The verification function reports a metric named `gitlab_teleport_backup_test_results`.
This metric is a [Gauge](https://prometheus.io/docs/concepts/metric_types/#gauge)
that indicates `1` when a restoration operation is successful and `0` when it fails.

Since these functions are short-lived jobs that run and exit quickly, they cannot be scraped by Prometheus directly.
Instead, we need to explicitly [push](https://prometheus.io/docs/practices/pushing/)
these metrics to a [Pushgateway](https://github.com/prometheus/pushgateway).
Pushgateway is a long-lived service that collects metrics from short-lived jobs
via a simple [HTTP API](https://github.com/prometheus/pushgateway?#api)
and exposes them at the `/metrics` endpoint, allowing Prometheus to scrape them as usual.

In each of `gprd`, `gstg`, and `ops` environments, we run a compute instance named `blackbox`.

- [blackbox-01-inf-gprd.c.gitlab-production.internal](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base-blackbox.json)
- [blackbox-01-inf-gstg.c.gitlab-staging-1.internal](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gstg-base-blackbox.json)
- [blackbox-01-inf-ops.c.gitlab-ops.internal](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/ops-base-blackbox.json)

 This instance runs a Prometheus Pushgateway as a [Systemd](https://systemd.io) service via the
 [gitlab-prometheus::pushgateway](https://gitlab.com/gitlab-cookbooks/gitlab-prometheus/-/blob/master/recipes/pushgateway.rb) recipe.
 The Pushgateway is listening on port `9091`.

We need to access the `blackbox` instance in the `ops` environment via `http://blackbox.int.ops.gitlab.net:9091`. This is an internal address,
so we must find a way to connect to it from the Teleport Google projects (`gitlab-teleport-production` and `gitlab-teleport-staging`).

- TODO: [Configure a Pushgateway](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/077c5ad2d2ebb2e7a217e965bb30da506bbb5907/modules/teleport-backup/functions/firestore-verify/index.js#L25)

##### Email Notifications

If a restoration operation fails, an email notification will be sent to the <production-engineering-team@gitlab.com> group using our Mailgun account.
We have generated an API key for each Teleport instance (`gitlab-teleport-production` and `gitlab-teleport-staging`).
The API keys are stored in our 1Password *DevOps Vault* under a Login named "Teleport".

The Mailgun API key is accessible to the `verify` Cloud Function in each environment via a secret named `mailgun_api_key` in Google Secret Manager.
This setup is done manually for ease of access,
though you can also store these keys in Vault and replicate them in Google Secret Manager using Terraform.
If you regenerate any Mailgun API keys, you must manually update the `mailgun_api_key` secret in Google Secret Manager and
then update the secret version for the Cloud Function
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/077c5ad2d2ebb2e7a217e965bb30da506bbb5907/modules/teleport-backup/verify.tf#L67).

### Troubleshooting

**Functions are Not Updated After Terraform is Applied**

If you make changes to the function source code and apply them in your merge request (using Atlantis or Terraform in pipelines),
you may find that in the Google Cloud Console, your changes are not reflected.

To resolve this issue, go to Cloud Storage and delete the `gitlab-teleport-staging-cloud-functions` bucket
and another bucket starting with `gcf-v2-sources-`. Then, delete the function from the Google Cloud Functions web console.
Finally, run `terraform init` and `terraform apply` from the `main` branch of `config-mgmt` locally to redeploy all the resources.
