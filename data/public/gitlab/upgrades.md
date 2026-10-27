# Upgrading Monitoring Components

Upgrading monitoring components requires changes in a few different places, but is standard from release-to-release.

Links to releases:

* [Grafana](https://github.com/grafana/grafana/releases)
* [Prometheus](https://github.com/prometheus/prometheus/releases)
* [Thanos](https://github.com/thanos-io/thanos/releases)

Links to various exporter releases:

* [beat_exporter](https://github.com/trustpilot/beat-exporter/releases)
* [blackbox_exporter](https://github.com/prometheus/blackbox_exporter/releases)
* [consul_exporter](https://github.com/prometheus/consul_exporter/releases)
* [ebpf_exporter](https://github.com/cloudflare/ebpf_exporter/releases)
* [elasticsearch_exporter](https://github.com/justwatchcom/elasticsearch_exporter/releases)
* [haproxy_exporter](https://github.com/prometheus/haproxy_exporter/releases)
* [imap_mailbox_exporter](https://ops.gitlab.net/ahmadsherif/imap-mailbox-exporter)
* [influxdb_exporter](https://github.com/prometheus/influxdb_exporter/releases)
* [mtail](https://github.com/google/mtail/releases)
* [node_exporter](https://github.com/prometheus/node_exporter/releases)
* [pgbouncer_exporter](https://github.com/prometheus-community/pgbouncer_exporter/releases)
* [postgres_exporter](https://github.com/prometheus-community/postgres_exporter/releases)
* [redis_exporter](https://github.com/oliver006/redis_exporter/releases)
* [smokeping_prober](https://github.com/SuperQ/smokeping_prober/releases)
* [stackdriver_exporter](https://github.com/prometheus-community/stackdriver_exporter/releases)
* [statsd_exporter](https://github.com/prometheus/statsd_exporter/releases)

## Monitoring

Monitoring components meta-monitor each other, but some care is needed to ensure we don't have gaps in observability.

### General

Most services expose a `SERVICE_build_info` that can be used to monitor the progress of the rollout. For example, [`prometheus_build_info`][prometheus_build_info].

Similarly, most services expose [`process_start_time_seconds`][process_start_time_seconds].

It's also worth checking the standard [`up`][up] metric.

### Prometheus/Thanos

The [monitoring-overview](https://dashboards.gitlab.net/d/monitoring-main/monitoring-overview) dashboard has a lot of details about Thanos and Prometheus metrics.

## Pre-Change Steps

Create an [infrastructure issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/new) if there isn't one yet.

The issue should detail:

* The components being upgraded.
* Any breaking changes from the release notes.
* Any significant features/improvements being rolled out.

Prepare upgrade MRs

* [ ] [Prometheus/Thanos/Pushgateway in Chef](https://gitlab.com/gitlab-cookbooks/gitlab-prometheus)
* [ ] [Prometheus in ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/prometheus/)
* [ ] [Grafana in ArgoCD](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/grafana/)
* [ ] [Various Exporters](https://ops.gitlab.net/gitlab-cookbooks/gitlab-exporters)
* [ ] [mtail in Chef](https://gitlab.com/gitlab-cookbooks/gitlab-mtail)
* [ ] [mtail docker image for GKE](https://ops.gitlab.net/gitlab-com/gl-infra/docker-mtail)
* [ ] [mtail docker image in argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/pubsubbeat/values.yaml)

Don't forget to bump cookbook versions when submitting cookbook changes.

## Change Steps

* [ ] Merge Chef MRs to the relevent cookbook.
* [ ] Wait for the cookbook publisher to post MRs to [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests)
* [ ] Merge non-prod chef-repo MR and wait for Chef to deploy.
* [ ] Verify new versions are deployed.
* [ ] Merge prod chef-repo MR and wait for Chef to deploy.
* [ ] Verify new versions are deployed.
* [ ] Merge Helmfile MRs.
* [ ] Verify new versions are deployed.

## Post-Change Steps

* [ ] Verify services are operating and no alerts are firing.
* [ ] Verify the [service metrics](#monitoring) are healthy.

## Rollback

* [ ] Prepare and submit rollback MRs for Chef/Helmfiles
* [ ] Verify service returns to normal.

[prometheus_build_info]: https://thanos.gitlab.net/graph?g0.range_input=1h&g0.max_source_resolution=0s&g0.expr=count%20by%20(env%2Cversion)%20(prometheus_build_info)&g0.tab=0
[process_start_time_seconds]: https://thanos.gitlab.net/graph?g0.range_input=1h&g0.max_source_resolution=0s&g0.expr=changes(process_start_time_seconds%7Bjob%3D%22prometheus%22%7D%5B1h%5D)&g0.tab=1
[up]: https://thanos.gitlab.net/graph?g0.range_input=1h&g0.max_source_resolution=0s&g0.expr=avg%20by%20(env)%20(up%7Bjob%3D%22thanos%22%7D)&g0.tab=0
