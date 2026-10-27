# OSQuery

## Summary

[OSQuery](https://osquery.io/) is an agent able to collect data from the underlying Operating System. It allows us to write SQL queries to explore operating system data, like running processes, loaded kernel modules, open network connections, browser plugins, hardware events or file hashes.

More details on the architecture can be found in the [handbook page](https://internal.gitlab.com/handbook/security/product_security/infrastructure_security/tooling/osquery/).

## Monitoring/Alerting

The most likely issue deriving from the OSQuery rollout might be related to an eventual performance penalty on the underlying hosts.

Spikes in CPU and/or memory usage can be detected by standard monitoring already in place on such hosts. For example, this [Grafana dashboard](https://dashboards.gitlab.net/d/fjSLYzRWz/osquery?orgId=1&refresh=1m&var-environment=gprd) could be helpful to identify the hosts where `osqueryd` is using the most CPU, memory or IO.

In addition, an [alert has been created](../../legacy-prometheus-rules/osquery.yml) to trigger
whenever the `osqueryd` process is using more than 10% CPU.

## Troubleshooting

:warning: If you believe that OsQuery is leading to performance issues on the server, it is 100% ok to disable it and investigate later. Please create an issue and tag `@gitlab-com/gl-security/security-assurance/team-commercial-compliance` :warning:

Historically, all previous deployments of osquery have resulted in performance issues in production. Here are some issues from reference:

* [osqueryd is leading to performance issues on small instances](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/15110) - `node_schedstat_waiting_seconds_total` raising because of osquery (more processes to be run than CPU time available to handle them).
* [\[RCA\] osqueryd consuming too many resources in production](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/6522) - Both CPU and Disk IO raising (looks like there was a bug on osquery).
* [osquery is filling up the root fs](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/6434) - osquery was getting a lot of data for the `process_file_events` table. This was disabled.

### How to disable OSQuery

In case any performance or any other issues observed with OSQuery and it is impact the production we can always disable it.

Following are the steps to disable OSQuery.

* Navigate to the [Chef Repo Roles](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/roles).
* Open the role targetting specific environment or service for which the OSQuery needs to be disabled.
* Set the osquery enabled flag to `false`

  ```json
   "osquery": {
      "enabled": false,
   }
   ```

   Refer sample [MR](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/merge_requests/1519/diffs).

### Service Management

The `osqueryd` service can be controlled like any other systemd service:

```
$ service osqueryd status
● osqueryd.service - The osquery Daemon
   Loaded: loaded (/usr/lib/systemd/system/osqueryd.service; enabled; vendor preset: enabled)
   Active: active (running) since Mon 2021-07-19 11:20:42 UTC; 26min ago
  Process: 27572 ExecStartPre=/bin/sh -c if [ -f $LOCAL_PIDFILE ]; then mv $LOCAL_PIDFILE $PIDFILE
  Process: 27569 ExecStartPre=/bin/sh -c if [ ! -f $FLAG_FILE ]; then touch $FLAG_FILE; fi (code=e
 Main PID: 27575 (osqueryd)
    Tasks: 18
   Memory: 57.7M
      CPU: 2.895s
   CGroup: /system.slice/osqueryd.service
           ├─27575 /usr/bin/osqueryd --flagfile /etc/osquery/osquery.flags --config_path /etc/osquery/
           └─27587 /usr/bin/osqueryd
```

## Links to further Documentation

* [gitlab-osquery](https://gitlab.com/gitlab-cookbooks/gitlab-osquery)
* [OSQuery | InfraSec Wiki](https://gitlab.com/groups/gitlab-com/gl-security/security-operations/infrastructure-security/-/wikis/Tooling/OSQuery)
* [Main OSQuery cookbook](https://supermarket.chef.io/cookbooks/osquery)
* [Palantir's OSQuery Configuration](https://github.com/palantir/osquery-configuration)
