# Kibana exercises

## Beginner

### Create a Visualisation based on a search in Discover

### Get percentiles of x requests

### Get time spent in gRPC calls

Useful for:

- analyzing which method runs the most often

## Advanced

### Get the number of requests sent from every ip address

Useful for:

- searching for DoS type of behavior

answer:

- Visualization
- data table
- metric: count
- buckets: split rows -> Terms -> json.remote_ip.keyword   (keyword because you want to use an Elastic field that hasn't been split into separate tokens)
