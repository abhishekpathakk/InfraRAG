# Chef troubleshooting

## Symptoms

1. HAProxy is missing workers:

    ```
    lb7.cluster.gitlab.com HAProxy_gitlab_443/worker4.cluster.gitlab.com is UNKNOWN - Check output not found in local checks
    ```

2. Nodes are missing chef roles:

    ```
    jeroen@xps15:~/src/gitlab/chef-repo$ bundle exec knife node show worker1.cluster.gitlab.com
    Node Name:   worker1.cluster.gitlab.com
    Environment: _default
    FQDN:        worker1.cluster.gitlab.com
    IP:          10.1.0.X
    Run List:
    Roles:
    Recipes:
    Platform:    ubuntu 16.04
    Tags:
    ```

3. Knife ssh does not work:

    ```
    bundle exec knife ssh "name:worker1.cluster.gitlab.com" "uptime"
    WARNING: Failed to connect to  -- Errno::ECONNREFUSED: Connection refused - connect(2)
    ```

## Resolution

1. Check if the workers have the chef role `gitlab-cluster-worker`. HAProxy config is generated with a chef search on this specific role.

    ```
    bundle exec knife node show worker1.cluster.gitlab.com
    ```

    If not restore the worker via `knife node from file`:

    ```
    bundle exec knife node from file worker1.cluster.gitlab.com.json
    ```

    Run chef-client on the node. When the chef-client run is finished on the nodes force a chef-client run on the load balancers to regenerate the haproxy config with the workers:

    ```
    bundle exec knife ssh -p2222 -a ipaddress role:gitlab-cluster-lb 'sudo chef-client'
    bundle exec knife ssh -p2222 -a ipaddress role:gitlab-cluster-lb-pages 'sudo chef-client'
    ```

2. See resolution steps at point 1.

3. Check if the ipnumber is correct for the node:

    ```
    bundle exec knife node show worker1.cluster.gitlab.com

    ```

    If ipaddress contains a wrong public ip update /etc/ipaddress.txt on the node and run chef-client

    If ipaddress contains a private (local) ip make sure /etc/ipaddress.txt is set and the node has at least the chef role base-X where X is the OS type like debian etc. check chef-repo/roles/base-* for all current base roles.

## Alerts

### Chef client failures have reached critical levels

Alert name: ChefClientErrorCritical
Alert text: At least 10% of type TYPE are failing chef-runs

What to do:

1. Find one of the nodes that is affected
   * The alert is summarized; click the link to the prometheus graph from the alert (to get to the alerting environment easily), and adjust the query to just be `chef_client_error > 0`.  It should list a metric for each node that is currently broken, from which you can select one of the type that is alerting.  There will often be some correlation/commonality that may stand out and allow you to select a suitable first candidate.
   * Alternatively you can use [Thanos](https://thanos.gitlab.net/graph?g0.expr=count(chef_client_error%20%3E%200)%20by%20(fqdn%2C%20env)&g0.tab=1&g0.stacked=0&g0.range_input=8w&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D) which will list the nodes in each environment
1. On that node, inspect the chef logs (`sudo grep chef-client /var/log/syslog|less`) to determine what's broken.

* It could be anything, but td-agent and incompatible gem combinations is common.  In that case you can use `td-agent-gem` to manually adjust installed versions until the list of gems, often google-related, are all compatible with each other (compare to a still functional node for versions if necessary).  Or delete all the installed gems and start again (running chef-client may bootstrap things again in that case).

### Overriding Alerts when Chef Cannot be Repaired

There may be times where you cannot repair Chef, but you want to stop the paging.
[This incident](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/19048) is an example of a situation where bad Chef runs were the last run before disabling chef-client.
We want to remove the alerts for clarity until the root cause can be fixed.
The Prometheus Node Exporter stores chef-client metrics in `/opt/prometheus/node_exporter/metrics/chef-client.prom`, and we can over-write this files data, specifically the value in `chef_client_error`.

Here is an example command to clear a single VMs chef-client error.

```bash
$ sudo sed -i "s/chef_client_error 1.0/chef_client_error 0.0/" /opt/prometheus/node_exporter/metrics/chef-client.prom"
```

## Troubleshoot Chef weirdness

Some times you need to understand why a `knife` command fails with Ruby errors.
The best way to figure out what is going on is to enable debugging output for the `knife` commnand:

```shell
bundle exec knife user -VV show _username_
```

This will dump a lot of output, and in case of a Ruby exception it will also print the full trace.

Another interesting step to run when troubleshooting is checking what commands were sent to Chef, to do so just grep nginx access log for relevant information

For example, search actions performed by a given user:

```shell
grep '"janedoe"' /var/log/opscode/nginx/access.log
```

Then look for POST or PUT methods to sample changes.

## Problem with not encrypted vault item during Chef run

Following error can occur `<role>/<vault> is not encrypted with your public key. Contact an administrator of the vault item to encrypt for you!` when you are trying to add role (`role with vault`) with vaults to new node (`new node`). If node or role does not have them, following error can occur.

In this case you have to execute the command:

```shell
rake add_node_secrets[<new node fqdn>, <role with vault>]
```
