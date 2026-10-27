# Container Registry Database Index Bloat

This document is a condensed summary of the troubleshooting and corrective steps taken while investigating [gitlab-com/gl-infra/capacity-planning#39](https://gitlab.com/gitlab-com/gl-infra/capacity-planning/-/issues/39) - the first potential index bloat saturation for the Container Registry database.

## Metrics

The Prometheus base query used for database index bloat forecasts is `gitlab_component_saturation:ratio{type="patroni-registry", component="pg_btree_bloat"}`. We can easily visualize the overall bloat trend in Thanos using [this query](https://thanos.gitlab.net/graph?g0.expr=max_over_time(%0A%20%20gitlab_component_saturation%3Aratio%7Btype%3D%22patroni-registry%22%2C%20environment%3D%22gprd%22%2C%20component%3D%22pg_btree_bloat%22%7D%5B1h%5D%0A)&g0.tab=0&g0.stacked=0&g0.range_input=1w&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D).

The query above can be used to identify the overall bloat. To see the estimated bloat for individual indexes, we can use the `gitlab_database_bloat_btree_bloat_size` metric.

The above metrics are fed by the bloat estimation queries from [github.com/ioguix/pgsql-bloat-estimation](https://github.com/ioguix/pgsql-bloat-estimation). Therefore, and although it can be useful as a complement, when dealing with index bloat alerts, it is preferred to rely on the metrics above rather than other estimation mechanisms, such as [`pgstatindex`](https://www.postgresql.org/docs/current/pgstattuple.html).

## Identifying Top Bloated Indexes

We can see the top 100 most bloated indexes using [this query](https://thanos.gitlab.net/graph?g0.expr=topk(100%2C%20sum%20by%20(query_name)%20(avg_over_time(gitlab_database_bloat_btree_bloat_size%7Bjob%3D%22gitlab-monitor-database-bloat%22%2C%20env%3D%22gprd%22%2Cstage%3D%22main%22%2Ctype%3D%22patroni-registry%22%7D%5B58m%5D)))&g0.tab=1&g0.stacked=0&g0.range_input=1w&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D).

## Fixing Index Bloat

The easiest and safest way to fix index bloat is by concurrently reindexing top bloated indexes.

[gitlab-com/gl-infra/capacity-planning#39](https://gitlab.com/gitlab-com/gl-infra/capacity-planning/-/issues/39) was the first time this need arose. If it occurs frequently enough in the future, we may want to pursue periodic/automatic reindexing on the application side. Until then, we should:

1. Identify top 100 most bloated indexes, as described in the previous section;
1. Raise a Production Change Request to concurrently reindex these indexes. Follow [gitlab-com/gl-infra/production#8175](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8175) as example.

If reindexing the top 100 is not enough, then we can move further and target the next 100. The majority of the registry tables have 64 partitions, so there are hundreds of indexes we can target.
