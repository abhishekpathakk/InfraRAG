# Google Cloud Snapshots

GCP snapshots are necessary to meet our RPO/RTO targets for the Gitaly service and our RTO for Patroni since using them speeds up recovery. The first instance in each server fleet will also have a snapshot taken of it's OS disk to help reduce the amount of time spent provisioning replacement instances.

## GCP [Scheduled Snapshots](https://docs.cloud.google.com/compute/docs/disks/scheduled-snapshots)

Automates the creation and the cleaning-up of disk snapshots.

- For all Gitaly storage nodes our default policy is to take a disk snapshot every 1 hour
- For database nodes a cron job is used to take a disk snapshot every 1 hour
- For all other nodes that take scheduled snapshots we default to every 4 hours

The default retention for disk snapshots is 14 days.

See the [alert playbook](alerts/GCPScheduledSnapshots.md) for information on troubleshooting issues with scheduled snapshots.

## Manual Snapshots (initiated through the API)

For Patroni we take manual snapshots with cron job that is configured in the Patroni Chef cookbook.
For more details see the [gcs-snapshot runbook for Patroni](../patroni/gcs-snapshots.md)
