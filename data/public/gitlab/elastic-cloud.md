# Elastic Cloud

## Quick start

### Elastic Cloud Web UI

<https://cloud.elastic.co/deployments>

Login using credentials in 1password, Vault: "Production", Login entry called: "Elastic Cloud"

### Elastic Vendor Tracker

<https://gitlab.com/gitlab-com/gl-infra/elastic/-/issues>

## How-to guides

### Creating a logging cluster

1. Create the deployment in the [elastic-cloud](https://gitlab.com/gitlab-com/gl-infra/observability/elastic-cloud) repo:
    1. add an environment directory with a `deployment.yaml` (region, version, topology, VM sizes per tier, cluster settings), plus a provider block and module call in `infra/`, see that repo's README ("Adding a new cluster")
    1. approve the MR and comment `atlantis apply`, Atlantis creates the deployment and then merges
    1. save the `elastic` superuser password in 1password (rotate if necessary)
1. Create users and their roles using Kibana
    1. in the deployment page you'll see links to Elasticsearch, Kibana and APM
    1. click on the Kibana link and login using admin credentials (user: elastic, password: it should have been added to 1password during deployment creation)
    1. Create users: pubsubuser, log-proxy
1. Add [Index Lifecycle Management](../logging/README.md#index-lifecycle-management-ilm) policies and index templates as JSON files in the [elastic-cloud](https://gitlab.com/gitlab-com/gl-infra/observability/elastic-cloud) repo, see that repo's README ("Adding other resources", "Adding an index template"). Prefer [data streams](https://www.elastic.co/guide/en/elasticsearch/reference/current/data-streams.html) for new indices, set `"data_stream": true` in the index template.
1. If not using a data stream, initialize the alias and first index manually, this is a one-off data-plane call, not managed by Terraform:

    ```
    PUT /pubsub-<index_name>-inf-<env_name>-000001
    {
        "aliases": {
            "pubsub-<index_name>-inf-<env_name>": {
                "is_write_index": true
            }
        }
    }
    ```

    Data streams skip this step, Elasticsearch auto-creates the backing index when the first document arrives.
1. Start sending logs to the cluster
1. Configure index patterns in Kibana (logs have to be present in the cluster):

- where possible, use json.time (timestamp of the log) rather than timestamp (when the log was received by the cluster)
- it's currently impossible to configure index patterns through api: <https://github.com/elastic/kibana/issues/2310> and <https://github.com/elastic/kibana/issues/3709>

1. Check all ILM policies (in particular the ones for APM indices) and make sure that they use node attributes when moving shards between phase. You might also want to review times shards spend in different phases.

### Creating a cluster (general notes)

#### Unallocated system shards

Sometimes when you create a cluster there are unallocated shards belonging to system indices. One case when this can happen is when there are not enough nodes eligible for handling system indices. For example, in a hot-warm deployment, system shards are configured with replica=2 (which means there are 3 shards in total) and they need to be allocated to hot nodes. If your deployment has < 3 hot nodes you'll have unallocated shards.

In this situation you can create an additional template (so that it is applied over the default system indices templates) with `"order": 2` and `"auto_expand_replicas":"0-1"`. The template should have for example `"index_patters":["apm-7.3.0*"]` (so that it is applied over the default "apm-7.3.0" template). You will have to remember though to update the index pattern in this custom additional template whenever you upgrade to the next version, and also to remove it if you do move to >=3 hot nodes so that the desired 2 replicas can be achieved.

### Resizing a cluster

#### Adding new availability zones

<https://www.elastic.co/guide/en/cloud-enterprise/current/ece-resize-deployment.html>

Adding and removing availability zones was tested. elastic.co decides whether to have a dedicated VM for master or to nominate master from among the data nodes. The number of availability zones determines in how many zones there will be data nodes (you might actually end up with more VMs if elastic.co decides to run master on a dedicated node).

#### Resizing instances

Before resizing, you need to make sure the cluster is in a healthy state. If needed, release some disk space or reallocate shards to distribute cpu load more evenly. Otherwise, the resize might fail in the middle, as it happened in the past.

The way resizing works is new machines are created with the desired spec, they are then brought online, shards are moved across and once that is complete the old ones are taken offline and removed. This has worked very smoothly in the past.

We can scale up and down. Resizing is done live.

#### Failures caused by snapshoting

Resizing cannot succeed without a successful snapshot. This means that if Elastic Cloud is unable to take a snapshot (e.g. cluster is unhealthy), the resize will fail. It also means that if there is a snapshot in flight, the resize will fail.
