# GCPScheduledSnapshots

## Overview

### Covered Alerts

- GCPScheduledSnapshotsDelayed
- GCPScheduledSnapshotsFailed

Patroni nodes have two independent snapshot mechanisms. This runbook covers OS boot disk snapshots (GCPScheduledSnapshotsDelayed/Failed). If your alert is PatroniGCSSnapshotDelayed, that refers to Postgres data backups handled by a cron job on the backup replica — see [gcs-snapshot runbook for Patroni](../../patroni/gcs-snapshots.md) instead.

**Note on Patroni Nodes**
> OS-disk snapshots for Patroni nodes have been intentionally disabled ([config-mgmt!14436](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/14436) because they were not being used for their intended purpose (speeding up VM launches) and Hyperdisk does not support guest_flush, causing ~50% of snapshot attempts to fail.
> **Background:** Originally enabled ~2 years ago (config-mgmt!8889), the setting was not carried forward when v16/v17 clusters were created — only patroni-registry still had enable_os_disk_snapshots = true, which caused recurring alerts.
> **Fix:** enable_os_disk_snapshots = false was applied across all affected nodes. Postgres data backups are unaffected. If this alert fires again for a Patroni node, verify the setting has not been inadvertently re-enabled.

[Scheduled snapshots](https://docs.cloud.google.com/compute/docs/disks/scheduled-snapshots) in GCP are not running at their regular interval, or are failing. GCP snapshots are necessary to meet our RPO/RTO targets for the Gitaly service and our RTO for Patroni since using them speeds up recovery. If snapshots are not being taken consistently, we become at risk of excessive data loss in the event of a catastrophic failure, and missing RTO targets in the event we need to restore instances.

- For all Gitaly storage nodes our default policy is to take a disk snapshot every 1 hour.
- For all other nodes that take scheduled snapshots we default to every 4 hours.

Contributing factors to scheduled snapshot execution could include:

1. GCP Quota Limits: GCP enforces quotas on the number of snapshots that can exist at a given time. If we hit this value, snapshot execution will halt.
1. Transient API errors on GCP's side: While uncommon, occasionally Google will have a failure that is unrelated to us that results in a snapshot not being taken or failing.
1. Misconfigured guest OS settings when application-consistent snapshots are enabled: When the application-consistent setting is enabled for a snapshot, it is a requirement that the guest OS google-cloud agent be installed, and configured to allow the feature. If this is not done, the snapshot will result in error.
1. There is a problem preventing data from being collected from the Stackdriver Prometheus exporter.

If snapshot failures or delays are observed, you should check [Stackdriver logs](https://cloudlogging.app.goo.gl/8Rwb2zPRDxk1tRRM8) to determine the cause, and decide if any further action is necessary.

## Services

- [GCP snapshots runbook](../gcp-snapshots.md)
- Because snapshots are taken at the cloud infrastructure level, this alert may apply to a number of different services. You can refer to the logs in [Stackdriver](https://cloudlogging.app.goo.gl/8Rwb2zPRDxk1tRRM8) to find the affected disk, which should provide a hint as to which service the failure applies to. In some cases it may be necessary to refer to the [service-catalog]() to locate the appropriate service owner to determine the impact of missing snapshots.

## Metrics

- [gcp-snapshots.yml](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gcp-snapshots.yml) defines two alerts outside of the metrics-catalog. Both alerts use metrics scraped by the Stackdriver exporter.
  - GCPScheduledSnapshotsDelayed looks for a timeseries that indicates that snapshots have stopped appearing for a disk that was previously taking scheduled snapshots in the past week.
  - GCPScheduledSnapshotsFailed looks for any timeseries that represents a snapshot failure  in the environment.
- Under normal circumstances, we do not expect any snapshot failures, and the alert thresholds are set to reflect that.
- Metrics in Grafana:
  - [GCPScheduledSnapshotsDelayed](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22qzr%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22absent_over_time%28stackdriver_gce_disk_logging_googleapis_com_user_scheduled_snapshots%7Benv%3D%5C%22gprd%5C%22%7D%5B4h%5D%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
    - It is expected that this will return "No data" normally.
  - [GCPScheduledSnapshotsFailed](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22qzr%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22count%20by%20%28env%29%28stackdriver_gce_disk_logging_googleapis_com_user_scheduled_snapshots_errors%7Benv%3D%5C%22gprd%5C%22%7D%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
    - It is expected that this will return "No data" normally.
- [Stackdriver logs for successful snapshots](https://cloudlogging.app.goo.gl/yT9m73Mk3HCtVmHZA)
- [Stackdriver logs for snapshot errors](https://cloudlogging.app.goo.gl/8Rwb2zPRDxk1tRRM8)
- [GCP Quotas](https://console.cloud.google.com/apis/api/compute.googleapis.com/quotas)

## Alert Behavior

- The GCPScheduledSnapshotsFailed alert is scoped to the entire GPRD environment without other distinguishing labels, it is not recommended to create a silence unless the cause of the alert is understood and a resolution is in progress.
- The GCPScheduledSnapshotsDelayed alert may also fire if a snapshot schedule is paused or removed. If this is done intentionally, and the disk needs to stay around, silence the alert for the impacted disk for 1 week, and it will fall out of the query results.
- False positive alerts can occur when there is an issue ingesting Stackdriver exporter metrics into the monitoring system, resulting in a GCPScheduledSnapshotsDelayed alert.

## Severities

- The failure to take snapshots of our disks does not cause any immediate customer facing impact, instead, only exposes us to increased risk in the event of additional failures.
- Certain internal processes may run into issues if they depend on recent snapshots being available, such as automated database refresh tasks.
- If unsure, a good starting severity for this class of alerts would be `S3`

## Recent changes

It is unlikely that recent changes have caused this alert unless someone recently changed the snapshot configuration for that particular system.

## Troubleshooting

- Basic troubleshooting steps:
  - Determine if the alert is valid by cross referencing the prometheus metrics in Grafana with the [logs in Stackdriver](https://cloudlogging.app.goo.gl/8Rwb2zPRDxk1tRRM8)
  - If there are errors returned in the log, view the message and determine which disk it is impacting. The disk will be stored in the `protoPayload.response.targetLink` field in the log entry.
  - The message should indicate whether the error is due to quota limits being reached, a misconfigured quest OS, a transient GCP API failure, etc.

## Possible Resolutions

- Refer to this [incident relating to a misconfigured OS](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18171)
- Manually retry the failed snapshot:
  - If the errors in stackdriver recommend to retry e.g. `"Internal error. Please try again or contact Google Support. (Code: '-5418078226953242804')"`, we can look up the disk name of failed snapshot by going to 'response' -> 'error' -> 'targetLink' in stackdriver log message. For example `https://www.googleapis.com/compute/v1/projects/gitlab-production/zones/us-east1-c/disks/file-97-stor-gprd-data`, which has disk name as the last part of Uri `file-97-stor-gprd-data`.

    Then run following command to create the snapshot (replace `<disk_name>` with the actual name e.g. `file-97-stor-gprd-data`, and the `<zone>` with the disk's zone, can be found in [this list](https://console.cloud.google.com/compute/disks?referrer=search&project=gitlab-production)):

    ```shell
    gcloud --project gitlab-production compute disks snapshot <disk_name> --zone=<zone> --description="Retried manual snapshot for <disk_name>"
    ```

    The manually created snapshots will get cleaned up by a [scheduled cron job](https://ops.gitlab.net/gitlab-com/gl-infra/gitlab-restore/gitlab-production-snapshots/-/pipeline_schedules).
- Request a snapshot quota increase if that is what's indicated by the failure log.

## Dependencies

- [GCP](https://status.cloud.google.com/)
- [Mimir](../../mimir/README.md)
- [Stackdriver metrics](../../stackdriver/README.md)

## Escalation

- If the cause of the snapshot failure is not clear from the logs and manual retry attempts are not succeeding after a short period (one or two hours), it may be necessary to escalate.
- Slack channels where help is likely to be found: `#s_production_engineering`

## Definitions

- [Link to the definition of this alert for review and tuning](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gcp-snapshots.yml)
- [Link to edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/blob/mattmi/gcp-scheduled-snapshots-delayed-playbook/docs/disaster-recovery/alerts/GCPScheduledSnapshots.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related alerts](./)
- [Related documentation](https://gitlab.com/gitlab-com/runbooks/-/blob/mattmi/gcp-scheduled-snapshots-delayed-playbook/docs/disaster-recovery/gcp-snapshots.md)
