The GCP console has a useful set of dashboards they call Network Intelligence, that show details of networking performance and throughput within GCP that may otherwise be challenging to see (or, if we can gather the data ourselves, is easier to visualize here).

Some specific features that may be useful:

### Performance Dashboard

<https://console.cloud.google.com/net-intelligence/performance/dashboard/packet-loss?project=gitlab-production>

The two key things it shows are Packet loss and Latency.  This is an excellent place to look if we suspect some non-trivial network outage is occurring.  It has definitely correlated with past incidents (e.g. [this one](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/3282); there appears to be sporadic but low-rate background packet loss (< 0.05%, usually much less, and still often 0).  One big tip: click on the time-graph along the top and the zone-pair grid at the bottom will show if it's between specific pairs of zones, which may be a crucial clue in debugging an outage.

### Network Topology

<https://console.cloud.google.com/net-intelligence/topology?project=gitlab-production>

Pointy-clicky map of the GCP networks, including load balancers, peers, etc. Clicking on an item annotates the links to the other itesm with their current bandwidth, with graphs for total bandwidth to/from.  Items initially visible include External LBs, Internal LBs, Peer Networks, and Regions.  A search box for node can open up the Region to show the node and break down traffic to/from that node to other server groups and drill down to other nodes.  It can be a little slow, but the data is there.
