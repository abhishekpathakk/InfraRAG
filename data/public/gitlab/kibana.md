# Kibana

## Quick start

### Kibana URL

Kibana on logging clusters can be reached at:

- <https://log.gprd.gitlab.net>
- <https://nonprod-log.gitlab.net>

Kibana for other (e.g. indexing) clusters can be reached by going to Elastic Cloud web UI and clicking on the Kibana URL in the deployment's page. There is very rarely (never?) a need to access those instances so there is no forwarding configured for them.

### Timezone in Kibana

Before providing screens/information from Kibana, set/check that your timezone in Kibana is UTC. It will be easier to understand provided information for you and other team members.

  1. Click on `≡` icon on the top right corner.
  1. Expand `Management` section and under `Kibana` click on `Advanced Settings`.
  1. Make sure *Time zone* (`dateFormat:tz`) is set to `UTC`.

## How-to guides

### Discover application

#### Searching and analyzing logs (filtering)

<https://www.elastic.co/guide/en/kibana/current/field-filter.html>

#### Elastic Query DSL

<https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html>

#### Lucene Query Language

<https://www.elastic.co/guide/en/kibana/current/lucene-query.html>

#### Kibana Query Language

<https://www.elastic.co/guide/en/kibana/8.7/kuery-query.html>

### Dashboard and Visualizations

<https://www.elastic.co/guide/en/kibana/8.7/dashboard.html>

### Kubernetes

Look for assistance with Kubernetes Logs here:
[../kube/kubernetes.md](../kube/kubernetes.md)
