# Scaling Elastic Cloud Clusters

You are most likely re-sizing the hot data tier in Elasticsearch since all
ingestion takes place through that tier before being migrated to the warm tier.

## Logging into Elastic Cloud to manage deployments

* Log into the [Elastic Cloud Log In](https://cloud.elastic.co/) using the
  `ops-contact+elastic@gitlab.com` credentials and one-time password.
* Select the gear icon next to the deployment you want to scale (or manage).

Once you are managing a single deployment, take note that on the left are some
useful links:

* The `API Console` link is a convenient location to run API commands and see
  the responses.
* The `Edit` link allows modifcations to the deployment.
* The `Elasticsearch` link will show a list of instances with their size and
  health.

## Determine data tier size and growing the instance count

Generally, we have X number of instances in a deploment, and those instances
are evenly divided between two zones. We usually have a single replica of an
index, so we need our shard number for an index to be X/2 as well.

As an example, we may have 34 instances in our hot data tier. And our highest
throughput index types use a template that sets their shard size to 17 (which
is half of 34). An index with 17 shards and 1 replica and a limit of 1 shard
per node will need 34 instances.

Also, scaling up the number of instances is further complicated by how the
Elasticsearch data tier is sized. The sizing for a data tier is expressed as a
storage/RAM/vCPU value per zone and not as a number of instances (per zone or
overall).

To find the new size, look at a current hot tier instance and note it's RAM and
available disk space. For example, with 17 hot tier instances per zone, and
each having 1.88 TB of available disk, this is a total of 31.96 TB per zone.
This lines up with the current hot data tier sizing of 31.88 TB of space.

If we wanted to add 2 more instances per zone, we would take 1.88 TB of space
and multiply that by 19 to see how large we should make the data tier. This new
value is 35.72 TB per zone. In our sizing options, we would select:
`35.63 TB storage | 1.19 TB RAM | 187.3 vCPU`.

This same technique can be used with RAM. Generally, each step larger in the
list of data tier sizing options will add a single instance per zone.

Select the new size and save the new configuration under the `Edit` menu option
for the deployment. You can track the changes in the `Activity` section from
the menu on the right.

## Taking advantage of the new instances

Adding more instances will help as Elasticsearch will start to move some shards
on to the new instances. But, the number of instances being leveraged to ingest
data will still be bottlenecked by the number of shards for indices. Therefore
the indices need their shard value increased to match the number of instances in
a zone.

Even after these changes are made, it will take hours (if not a day or so) to
have the cluster fully using the new resources.

### Increase Index Template number_of_shards

When an index is created, it has a number of shards set that cannot be changed.
Once the current indices are rolled over and new data is being added to the new
index, it will use the values from the index templates. Index templates are
composed of tiers (`high`, `high_13`, `high_rails`, `medium`, `standard`, see
`environments/gitlab-logs-prod/index-template-composition-config.yaml` in the
[elastic-cloud](https://gitlab.com/gitlab-com/gl-infra/observability/elastic-cloud)
repo), each backed by a component template
(`environments/gitlab-logs-prod/component-templates/pubsub-logsdb-<tier>.json`)
that sets `number_of_shards`. The highest-throughput tier should match the
number of instances in a zone. So if we just set the number of instances to 19
per zone, this should probably match that value to maximize the number of
instances that can ingest logs from pubsubbeat.

If you are focusing on another tier, you should consider increasing those as
well.

[Example MR][examplemr]

### Increase Lifecycle total_shards_per_node

Once the indexes are migrated from the hot data tier to warm, the number of
shards for an index will not change, but the warm data tier (probably) has less
instances. We need to update the lifecycle policy for the right template level
to make sure we allow enough shards per instance to fit the new index size.

We can determine how many `total_shards_per_node` to set for the warm data tier
to accomodate the new number of shards by dividing the number of shards by the
number of instances in a zone in the warm tier. Right now, the warm tier has 5
instances per zone, so growing to a size of 19 (for example), would require a
warm tier instance to be able to host 3.8 shards. We round up to 4.

Create an MR in the [elastic-cloud](https://gitlab.com/gitlab-com/gl-infra/observability/elastic-cloud) repo to update these values:

* `number_of_shards` in the tier's component template, e.g. `environments/gitlab-logs-prod/component-templates/pubsub-logsdb-high.json` (hot phase also sets its own `routing.allocation.total_shards_per_node` there)
* `total_shards_per_node` (warm phase) in `environments/gitlab-logs-prod/index-lifecycle-policies/gitlab-infra-high-ilm-policy.json`

## Verifying Changes

You can make these API calls using the `API Console` in the Elastic Cloud Web
UI, inside the Kibana interface Management Dev Tools, or with curl.

### Index Template Shard Number

Show index templates to view sharding values. This example will show the gprd
rails index template. Look for the `number_of_shards` to very the new setting.

```
GET /_template/gitlab_pubsub_rails_inf_gprd_template
```

### New Index Shard Number

Identify the most recent index. The most recent index will have the highest
count value at the end of its name. This example query is for rails in gprd
to list all the indices.

```
GET /_cat/indices/pubsub-rails-inf-gprd*?s=index&h=index
```

Once you know the current index, you can explain it's ILM status to see when
the index was created. The `age` value should help to determine if this index
was created after the template updates were made.

```
GET <index>/_ilm/explain
```

Examining the index itself to see how many shards it is set to use. Looking at
the `number_of_shards` value should match the settings made to the template
earlier in this process.

```
GET <index>/_settings
```

[examplemr]: https://gitlab.com/gitlab-com/runbooks/-/merge_requests/5123/diffs#diff-content-19c1ff72f699959925cc1fb468bc3629949b90f9
