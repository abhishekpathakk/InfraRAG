# Measuring Recovery Activities

During the process of testing our recovery processes for Zonal and Regional outages, we want to record timing information.
There are three different timing categories right now:

1. Fleet specific VM recreation time
1. Component specific DR restore process time
1. Total DR restore process time

## Common measurements

### VM Provision Time

This is the time from when an apply is run on an MR to create new VMs until the apply completes successfully (i.e., the VMs are created and running).

This can be measured from the Atlantis apply timestamp to when the apply pipeline completes.

### Bootstrap Time

During the provisioning process, when a new VM is created, it executes a bootstrap script that may restart the VM.
This measurement might take place over multiple boots.
[This script](https://gitlab.com/gitlab-com/runbooks/-/blob/master/scripts/find-bootstrap-duration.sh) can help measure the bootstrap time.
This can be collected for all VMs during a gameday, or a random VM if we are creating many VMs.

## Gameday DR Process Time

The time it takes to execute a DR process. This should include creating MRs, communications, execution, and verification.
This measurement is a rough measurement right now since current process has MRs created in advance of the gameday.
Ideally, this measurement is designed to inform the overall flow and duration of recovery work for planning purposes.

## Gitaly

### VM Recreation Times

| Date | Environment | VM Provision Time | Bootstrap Time | Notes |
| ---- | ----------- | ----------------------- | -------------- | ----- |
| 2026-07-14 | GSTG | 00:24:24 | 00:04:34 | [Gameday change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22417), this time is calculated from the slowest Gitaly node in the recreation process. |
| 2026-01-26 | GSTG | 01:16:00 | 00:09:17 | [Gameday change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18627), this time is calculated from the slowest Gitaly node in the recreation process. There was an issue booting up the nodes, which took time to debug and fix. |
| 2024-10-21 | GPRD | 00:39:00 | 00:10:41 | [Gameday change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18645), the VM provision time is for 45 Production Gitaly VMs |
| 2024-10-15 | GSTG | 00:14:10 | 00:07:01 | [Gameday change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18627), this time is calculated from the slowest Gitaly node in the recreation process. |
| 2024-08-22 | GSTG | 00:14:49 | 00:07:07 | [Gameday change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18413), this time is calculated from the slowest Gitaly node in the recreation process. |
| 2024-07-10 | GSTG | 00:18:21 | 00:08:48 | [Change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18221) |
| 2024-06-20 | GPRD | 00:24:13 | 00:07:11 | Initial test of using OS disk snapshots for restore in GPRD. [Change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18157) |
| 2024-06-10 | GSTG | 00:14:21 | 00:08:01 | [Game Day change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18091) |

### Gameday Zonal Outage DR Process Time

| Date | Environment | Duration | Notes |
| ---- | ----------- | -------- | ----- |
| 2026-07-14 | GSTG | 02:38:00 | [Change Issue](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22417), Time difference is between the change::in-progress & change::complete labels being set it includes time required to create MRs and time taken to SSH connection to Staging. |
| 2026-01-26 | GSTG | 04:15:00 | [Change Issue](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21087), Time difference is between the change::in-progress & change::complete labels being set it includes time required to create MRs and time taken to SSH connection to Staging. |
| 2024-10-21 | GPRD | 02:05:00 | [Change Issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18645) , this was a limited Gameday that only measured creating and removing VMs |
| 2024-10-15 | GSTG | 01:38:00 | [Change Issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18627) , Time difference is between the change::in-progress & change::complete labels being set it includes time required to create MRs and time taken to SSH connection to Staging. |
| 2024-08-22 | GSTG | 02:07:00 | [Change Issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18413) , Time difference is between the change::in-progress & change::complete labels being set it includes time required to create MRs and time taken to create PAT and SSH connection to Staging. |
| 2024-07-10 | GSTG | 01:15:00 | [Change issue](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18221) |
| 2024-06-10 | GSTG | 01:20:00 | *Time difference is between the change::in-progress & change::complete labels being set. Doesn't include time to create MRs. |

## Patroni/PGBouncer

### VM Recreation Times

| Date | Environment | VM Provision Time | Bootstrap Time | Notes |
| ---- | ----------- | -------- | -------------- | ----- |
| 2024-08-28 | GSTG | 00:19:25 | 00:12:58 | [GSTG Patroni Gameday](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18412) |
| 2024-08-08 | GSTG | 00:20:49 | 00:10:57 | [GSTG Patroni Gameday](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18358) , [This is calculated from the slowest Patroni node among all the clusters.](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18358#note_2037567888) |
| 2024-08-06 | GPRD | 00:17:41 | 00:11:03 | GPRD Patroni [provisioning test](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18334) with the registry cluster. |
| 2024-04-25 | GSTG | HH:MM:SS | 00:06:00 | Collection of a Patroni bootstrap duration baseline while using OS disk snapshots. Terraform apply duration was not recorded. |
| 2024-04-25 | GSTG | HH:MM:SS | 00:35:00 | Collection of a Patroni bootstrap duration baseline while using a clean Ubuntu image. Terraform apply duration was not recorded. |
| 2025-07-21 | GSTG | 00:02:34 | 00:28:53 | [GSTG Patroni Gameday](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20047) |

### Gameday Zonal Outage DR Process Time

| Date | Environment | Duration | Notes |
| ---- | ----------- | -------- | ----- |
| 2024-08-28 | GSTG | 00:39:00 | For this [Gameday excersize on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18412) |
| 2024-08-08 | GSTG | 01:12:SS | For this [Gameday excersize on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18358) , attempted to create new patroni nodes in recovery zones , took longer than expected because we hit the snapshot quota |
| 2025-07-21 | GSTG | 01:12:00 | [GSTG Patroni Gameday](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20047) |

## HAProxy/Traffic Routing Zonal Outage DR Process Time

### VM Creation Times

| Date | Environment | VM Provision Time | Bootstrap time | Notes |
| ---- | ----------- | -------- | ---- | ----- |
| 2024-08-14 | GSTG | 00:14:40 | 00:13:15 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18356) |
| 2025-03-17 | GSTG | 00:09:00 | 00:23:50 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/19428) |
| 2025-10-02 | GSTG | 00:15:55 | 00:14:26 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20603) |
| 2026-01-19 | GSTG | 00:12:00 | 00:16:30 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21078) |
| 2026-04-28 | GSTG | 00:14:05 | 00:14:12 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21452) |
| 2026-08-17 | GSTG | 00:29:52 | 00:16:32 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22670). VM Provision Time measured from the Atlantis apply comment to Atlantis auto-merging the MR on successful apply. Unusually long compared with previous runs; the VMs themselves existed within ~75s and were in the TCP LBs by 10m, so most of the remaining time was the GKE `regional_cluster_zones` change draining node pools in the excluded zone. Bootstrap time is the slowest of the four `101` nodes (`haproxy-ci-101`, 992s). |

### Gameday Zonal Outage DR Process Time

| Date | Environment | Duration | Notes |
| ---- | ----------- | -------- | ----- |
| 2024-10-10 | GSTG | 01:30:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18662). First time run by a non-Ops team member |
| 2024-08-14 | GSTG | 00:53:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18356) |
| 2025-03-17 | GSTG | 01:22:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/19428) |
| 2025-10-02 | GSTG | 00:45:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20603) |
| 2026-01-19 | GSTG | 01:25:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21078). Actual time on changes was within expect range, but time spent dealing with personal machine issues, and unrelated pipeline failures added a few hours which have been disregarded for time tracking here. |
| 2026-04-28 | GSTG | 00:42:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21452) |
| 2026-08-17 | GSTG | 00:55:00 | [Game Day change issue on GSTG](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/22670). Includes ~12 min of local workstation issues (Ruby/`knife` version mismatch, stale `known_hosts` entries for the recycled `101` hostnames) and ~18 min diagnosing an incomplete first `disable-server` pass: the `101` nodes finished bootstrapping after step 6 had run, so they came up with the failed zone enabled and step 6 needed re-running. |

## CI Runner Zonal Outage DR Process Time

### VM Creation Times

| Date | Environment | Shard | VM Provision Time | Bootstrap time | Notes |
| ---- | ----------- | ----- | -------- | -------------- | ----- |
| 2024-08-29 | GPRD | 2xlarge | 00:08:20 | 00:03:59 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18752) |
| 2025-08-27 | GPRD | private | NA | NA | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20389) New VMs were not provisioned as part of this gameday, hence measuerments are not applicable. |
| 2026-01-21 | GPRD | private | NA | NA | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20958) + [Follow up](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/21136) New runner-manager VMs were not provisioned as part of this gameday, hence measurements are not applicable. |
| 2026-04-08 | GPRD | private | NA | NA | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21285). Timing for capacity increase: 32 mins (from MR preparation and merging to first successful jobs) |

### Gameday Zonal Outage DR Process Time

| Date | Environment | Shard | Duration | Notes |
| ---- | ----------- | ----- | -------- | ----- |
| 2024-08-29 | GPRD | 2xlarge | 01:01:00 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18752) |
| 2025-04-21 | GPRD | private | 00:49:00 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/19407) |
| 2025-06-26 | GPRD | private | 00:41:00 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20020) |
| 2025-08-27 | GPRD | private | 00:41:00 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/20389) It took 41 minutes from the sart of the CR until all runner-manager VMs appeared in Grafana |
| 2026-01-21 | GPRD | private | 00:23:00 | [Game Day change issue on GPRD](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/20958) + [Follow up](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/21136) It took 23 minutes from submitting a config change MR until all runner-manager VMs appeared in Grafana |
