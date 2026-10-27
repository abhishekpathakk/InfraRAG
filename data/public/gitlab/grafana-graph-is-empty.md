# Grafana graph is empty

1. Click on the graph title and select "Edit"
1. Try setting the data source to Global, see if this fixes the problem.
1. If not, try expanding the time range (say, 1 day, 1 week or even 1 month). If you got a graph then it could mean that:
  a. The metric exporter stopped working at some point in the past, or no more nodes are using this exporter anymore.
  b. The metric got renamed.
