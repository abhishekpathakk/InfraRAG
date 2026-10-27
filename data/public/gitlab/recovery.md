# Zonal and Regional Recovery Guide

## Identify the Scope

Identifying the scope of the degredation is key to knowing which recovery processes to exceute to restore services.
This will most likely require combining information from the cloud provider and our metrics.

| Symptoms | Possible Actions |
| --- | --- |
| GCP declares a zone is unavailable | Perform Zonal recovery for all components |
| GCP declares a region is unavailable | Perform Regional recovery for all components |
| Unable to provision new VMs in a zone | Perform a limited zonal recovery for traffic routing and possibly CI-Runners |

### Components

The disaster recovery processes break down sections of similarly implemented services into components.
Components are also a good way to break down the entire site into smaller sections that can be delegated during large disruptions for parallel work.
This is a simplified list of key components to focus on:

- Gitaly
- Patroni/PGBouncer
- HAProxy/Traffic Routing
- CI Runners
- Redis
- Redis Cluster
- Regional GKE Clusters
- Zonal GKE Clusters
- CustomersDot
- Etc.

## Zonal Recovery

The Networking and Incident Management team validates the ability of recovery from a disaster that impacts a single availability zone.

In the unlikely scenario of a zonal outage on GitLab, several sets of work can be taken to restore GitLab.com to operational status by routing away from the zone that is degraded and spinning up new resources in working zones.
To ensure a speedy recovery, enlist help and delegate out these changes so they can be performed in parallel.

All recoveries start with a change issue using `/change declare` and selecting one of the following templates:

- `[change_zonal_recovery_gitaly](https://gitlab.com/gitlab-com/gl-infra/production/-/blob/master/.gitlab/issue_templates/change_zonal_recovery_gitaly.md)`
- `[change_zonal_recovery_patroni](https://gitlab.com/gitlab-com/gl-infra/production/-/blob/master/.gitlab/issue_templates/change_zonal_recovery_patroni.md)`
- `[change_zonal_recovery_haproxy](https://gitlab.com/gitlab-com/gl-infra/production/-/blob/master/.gitlab/issue_templates/change_zonal_recovery_haproxy.md)`

**Note**: If GitLab.com is unavailable, check the `Use ops.gitlab.net instead of gitlab.com` option when creating the change issue.

**Note**: When a zonal outage ends, exercise caution in falling back on previously down infrasrtucture. Some components (like Gitaly), may require incur more downtimes when falling back to the old zone.

## Regional Recovery

GitLab.com is deployed in single region, [us-east1 in GCP](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production/architecture/).
In the case of a regional outage, GitLab will restore capacity using the `us-central1` region.

The recovery will start with a change issue using `/change declare` and selecting the `change_regional_recovery` template.

**Note**: If the `us-east1` region is unavailable, it will be necessary to create a change issue on the Ops instance, so the `Use ops.gitlab.net instead of gitlab.com` option should be checked.

## Component Specific Context

These are short overviews for some of the components and how we can change them to keep GitLab.com working during outages and degredations.

### Draining HAProxy traffic to divert traffic away from the affected zone

HAProxy traffic is divided into multiple Kubernetes clusters by zone.
Services like `web`, `api`, `registry`, `pages` run in these clusters and do not require any data recovery since they are stateless.
In the case of a zonal outage, it is expected that checks will fail on the corresponding cluster and traffic will be routed to the unaffected zones which will trigger a scaling event.
To ensure that traffic does not reach the failed zone, it is recommended to divert traffic away from it by [draining the zone's servers through consul KV](../frontend/agent.md#draining-a-server).

### Reconfigure regional node pools to exclude the affected zone

To reconfigure the regional node pools, set `regional_cluster_zones` to the list of zones that are not affected by the zonal outage in Terraform for the regional cluster. For example, if there is an outage in `us-east1-d`:

[Example MR](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/4862)

```

  module "gitlab-gke" {
    source  = "ops.gitlab.net/gitlab-com/gke/google"
    ...
    regional_cluster_zones = ['us-east1-b', 'us-east1-c']
    ...
  }


```

### Database recovery using snapshots and WAL-G

- Patroni clusters are deployed across multiple zones within the `us-east1` region. In the case of a zonal failure, the primary should fail over to a new zone resulting in a short interruption of service.
- When a zone is lost, up to 1/3rd of the replica capacity will be removed resulting in a severe degradation of service. To recover, it will be necessary to provision a new replicas in one of the zones that are available.

To recover from a zonal outage, configure a new replica in Terraform with a zone override ([example](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/4603)).
The latest snapshot will be used automatically when the machine is provisioned.
As of `2022-12-01`, it is expected that it will take approximately [2 hours for the new replica to catch up to the primary](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16792) using a disk snapshot that is 1 hour old.

To see how old the latest snapshots are for Postgres use the `glsh snapshots list` helper script:

```

$ glsh snapshots list -e gprd -z us-east1-d -t 'file'
Shows the most recent snapshot for each disk that matches the filter looking back 1 day, and provides the self link.

Fetching snapshot data, opts: env=gprd days=1 bucket_duration=hour zone=us-east1-d terraform=true filter=file..

╭─────────────────────────────────┬──────────────────────┬────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ disk                            │ timestamp            │ delta  │ selfLink                                                                                                                                 │
╞═════════════════════════════════╪══════════════════════╪════════╪══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╡
│ file-23-stor-gprd-data          │ 2023-04-06T14:02:53Z │ 01h60m │ https://www.googleapis.com/compute/v1/projects/gitlab-production/global/snapshots/file-23-stor-gprd-d-us-east1-d-20230406140252-crc9hy33 │
│ file-26-stor-gprd-data          │ 2023-04-06T13:04:27Z │ 02h60m │ https://www.googleapis.com/compute/v1/projects/gitlab-production/global/snapshots/file-26-stor-gprd-d-us-east1-d-20230406130426-pt2f6fwl │
...

```

**Note**: Snapshot age may be anywhere from minutes to 6 hours.

### Gitaly recovery using disk snapshots

- When a zone is lost, all projects on the affected node will fail. There is no Gitaly data replication strategy on GitLab.com. In the case of a zone failure, there will be both a significant service interruption and data loss.
- There are about 10 legacy `HDD` Gitaly VMs that are not currently tested for recovery during a zonal outage.

To recover from a zonal outage, new Gitaly nodes can be provisioned from disk snaphots.
Snapshots are used to minimize data loss which will be anywhere from minutes to 1 hour depending on when the last snapshot was taken.

A [script](https://gitlab.com/gitlab-com/runbooks/-/tree/master/scripts/disaster-recovery) exists that can be used to generate MRs for Terraform, Chef, and GKE to replace Gitaly VMs that are part of the Gitaly Multiproject pattern.
The script automatically attempts to allocated replacement Gitaly VMs equally into the other good zones.
The MRs this script generates is capable of updating the GitLab configuration in GitLab.com for GKE pods and Chef managed VM nodes.

### Redis

The majority of the load from the GitLab application is on the Redis primary.
After a zone failure, we may want to start provisioning a new Redis node in each cluster to make up for lost capacity.
This can be done in Terraform with a zone override (setting `zone`) on the corresponding modules in Terraform.

One of the Redis clusters, "Registry Cache" is is Kubernetes. To remove the failed zone, reconfigure the regional cluster with `regional_cluster_zones` as explained in the Kubernetes section above.

**Warning**: Provisioning new Redis secondaries may [put additional load on the primary](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16791#note_1229590289) and should be done with care and only if required to add capacity due to saturation issues on the remaining secondaries.
