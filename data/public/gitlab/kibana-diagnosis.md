# Diagnosis with Kibana

## Background

- Logging pipeline architecture ([complex diagram](../logging/README.md#concepts))
  - Elasticsearch / Kibana
    - Retention: 7 days retention
    - Logs Flow: Application => Log file => FluentD => Pub/Sub => Pubsubbeat => Elasticsearch
  - GCS archive
    - Retention: 1 year
    - Logs Flow: Application => Log file => FluentD => Stackdriver => Archive GCS bucket
    - Most useful for security-related RCAs.
    - Can be imported into BigQuery for analysis.
- Logging cluster: <https://log.gprd.gitlab.net>

## Exploration

### Which indices correspond to which services?

Take a look at the list of indices in Kibana and try to find out which indices
correspond to which service.

<details>

- `pubsub-rails-inf-gprd*` web, git and api traffic
- `pubsub-consul-inf-gprd*` service discovery, DB failover
- `pubsub-gitaly-inf-gprd-*` Git repository Storage
- `pubsub-gke-inf-gprd*` meta Kubernetes logs
- `pubsub-gcp-events-inf-gprd-*` GCP maintenance events
- `pubsub-kas-inf-gprd*` Server side GitLab Relay (KAS)
- `pubsub-mailroom-inf-gprd-*` receiving emails
- `pubsub-monitoring-inf-gprd-*` Prometheus & Thanos meta monitoring
- `pubsub-pages-inf-gprd*` Logs for Gitlab-Pages
- `pubsub-postgres-inf-gprd-*` Patroni hosts
- `pubsub-pubsubbeat-inf-gprd-*` meta log of logging pipeline
- `pubsub-puma-inf-gprd*` rails webservice logging (not requests)
- `pubsub-pvs-inf-gprd*` Pipeline Validation Service
- `pubsub-redis-inf-gprd*` Redis and Sentinel
- `pubsub-registry-inf-gprd*` Registry traffic + monitoring
- `pubsub-runner-inf-gprd*` All runners logs
- `pubsub-shell-inf-gprd*` - SSH traffic to Gitaly
- `pubsub-sidekiq-inf-gprd*` - Background jobs queues logs
- `pubsub-system-inf-gprd*` - Host-level syslog
- `pubsub-workhorse-inf-gprd-*` - Proxy in front of rails. All traffic.
- `release_tools-*` Deployer (owned by Delivery).

</details>

### Explore the schema of the most important indices

These tend to be high-volume indices for critical path services in our
infrastructure.

- `pubsub-rails-inf-gprd*`
- `pubsub-gitaly-inf-gprd-*`
- `pubsub-sidekiq-inf-gprd*`
- `pubsub-workhorse-inf-gprd-*`

### Finding things in logs, filtering on fields, looking at value distributions

- Find all 5xx errors on the API fleet over the last 6 hours
- What is the distribution of traffic served by api vs git vs web?
- How much traffic does workhorse absorb and not pass through to rails?
- Which endpoints are receiving the most traffic?
- Which users are sending the most requests?

### Correlation across indices via `correlation_id` (tracing)

- Make a request to GitLab.com, find the correlation_id from the HTTP response header
- Go to the Correlation dashboard in kibana
- Look at which services are being traversed in the process
- Where is most of the time being spent?
- Which services are being hit multiple times per request?

### Cross-links from grafana service dashboards

- Go to the api service in grafana and find cross-links on the right hand side
- Try out failed requests, slow requests, and visualizations
- Find a sample slow or failed request and trace it via the correlation dashboard

### Visualization and time-series top-k queries

- Modify existing visualizations to perform a top-k analysis
- Which users are using the most request time on rails processes?
- Which projects are using the most CPU time on gitaly?
- Which sidekiq jobs are processing the most jobs?

## Resources

- [Production logging cluster](https://log.gprd.gitlab.net/app/kibana)
- [Logging runbook](../logging/README.md#concepts)
- [Kibana docs](https://www.elastic.co/guide/en/kibana/current/index.html)
