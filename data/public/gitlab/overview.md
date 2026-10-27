# ErrorTracking main troubleshooting document

## Overview

Customers take advantage of the [Error Tracking](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/#clickhouse-datastore) feature by configuring their application using the sentry-sdk to send error tracking data to GitLab.com opstrace instance.

At this time the service is in the [Beta feature stage](https://docs.gitlab.com/policy/development_stages_support/#beta-features), and is not recommended for production use.
All failures related to this service should be directed to the [Monitor:Platform Insights Group](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/), `#g_monitor_platform_insights` in Slack.

Opstrace maintains their own [runbooks](https://gitlab.com/gitlab-org/opstrace/runbooks/) that have more details about the service,
also see the [Clickhouse readiness review](https://gitlab.com/gitlab-com/gl-infra/readiness/-/tree/master/library/database/clickhouse)

### Infrastructure

Production and Staging environments are hosted outside of Infrastructure managed GCP, so for now there are no SLAs set for the service.
See [Clickhouse infrastructure in GCP](https://gitlab.com/gitlab-com/gl-infra/readiness/-/tree/master/library/database/clickhouse#gcp) for details.

### Metrics and Monitoring

Because the infrastructure is hosted outside of our Production GCP account, there are no dashboards or alerts for this service, or for the Clickhouse backing store.

Some metrics are available to query directly in Thanos:

- [Pod health](https://thanos.gitlab.net/graph?g0.expr=sum(up%7Bcontainer%3D%22errortracking-api%22%2Cenvironment%3D%22opstrace-prd%22%7D)&g0.tab=1&g0.stacked=0&g0.range_input=1h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)
- [Request success percentage](https://thanos.gitlab.net/graph?g0.expr=100%20-%20100*(sum(http_requests_total%7Bcode!%3D%22200%22%2Ccontainer%3D%22errortracking-api%22%2Cenvironment%3D%22opstrace-prd%22%7D%20or%20vector(0))%2Fsum(http_requests_total%7Benvironment%3D%22opstrace-prd%22%2Ccontainer%3D%22errortracking-api%22%7D))&g0.tab=1&g0.stacked=0&g0.range_input=1h&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D)

### Alerting

Currently, there is no alerting for this service
