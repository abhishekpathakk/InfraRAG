# HAProxyAgentConsulSyncStale

## Overview

[gitlab-haproxy-agent](https://gitlab.com/gitlab-com/gl-infra/gitlab-haproxy-agent)
runs on every haproxy node and answers haproxy agent-check probes with the
desired server state held in consul KV (see
[the agent runbook](../agent.md)).
This alert fires when the agent on a node has not completed a consul read in
15 minutes. Its consul watch normally returns at least every 5 minutes even
when nothing changed, so this means the watch is broken on that node.

There is no customer impact: the agent keeps answering haproxy from its last
synced copy, and haproxy keeps the last received state for each server. The
impact is operational. Desired-state writes to consul KV (drains, weight
changes) are not reaching the affected load balancer, so a drain issued
during an incident will not take effect there.

## Services

- [Service Overview](../README.md)
- Owner: [Production Engineering: Networking & Incident Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/networking-and-incident-management/)
- **Label**: gitlab-com/gl-infra/production~"Service::HAProxy"

## Diagnosis

On the affected node (the `fqdn` label):

```shell
systemctl status gitlab-haproxy-agent
journalctl -u gitlab-haproxy-agent --since -30min
curl -s localhost:9778/-/metrics | grep gitlab_haproxy_agent_kv
consul members   # is the local consul agent healthy?
```

The agent logs consul read failures with backoff. The usual causes are a
broken local consul agent or a consul cluster problem, in which case other
consul-dependent alerts will fire alongside this one.

## Remediation

- If the local consul agent is broken, fix that first. The agent recovers on
  its own once consul answers again.
- `systemctl restart gitlab-haproxy-agent` is safe at any time. While the
  agent is down or stale, haproxy keeps the last received state for every
  server. If the agent cannot sync at startup it exits, and systemd restarts
  it until consul answers.
- To verify recovery, watch the staleness reset:

  ```shell
  curl -s localhost:9778/-/metrics | grep kv_last_sync
  ```

- If a drain was issued while the node was stale, confirm it took effect
  after recovery via the stats socket (`show stat` via hatop or socat), or
  re-issue the KV write.
