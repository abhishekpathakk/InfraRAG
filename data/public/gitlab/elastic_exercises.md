# Elastic exercises

## Find an optimal size for a cluster that will be able to consume logs from one of the production Pub/Subs

- create a minimal deployment in Elastic Cloud, enable monitoring, forward monitoring metrics to the monitoring cluster
- make a change in terraform to create a pubsubbeat VM and a subscription
- configure pubsubbeat with credentials for the Elastic Cloud deployment
- silence alerts in alertmanager
- initialize the cluster (create ILM policy, templates, etc)
- observe the cluster health in the monitoring cluster
- resize the cluster and fix any errors with indices, unallocated shards, ILM errors

## resize the cluster

## trigger reallocation of failed shards
