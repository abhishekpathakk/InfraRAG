# gitlab-haproxy-agent: draining HAProxy servers via consul KV

[gitlab-haproxy-agent](https://gitlab.com/gitlab-com/gl-infra/gitlab-haproxy-agent)
runs on every HAProxy node and answers haproxy
[agent-check](https://docs.haproxy.org/2.8/configuration.html#5.2-agent-check)
probes with the desired server state held in consul KV. Writing one KV key
changes a server's state on every HAProxy in the environment within seconds,
with no reload, no chef converge, and no SSH to load balancers. It is the
only way server admin state is set: the TCP admin listener the old tooling
used is gone, and the server state file with it.

Design and history: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29645>

## The KV contract

```
gitlab-haproxy-agent/state/<backend>/<server> = ready | drain | maint | <weight>% (0-256)
gitlab-haproxy-agent/state/<group>            = same
```

An absent key means `ready`. Deleting the key is how a state is cleared.

Use `maint` for take-out-and-return work and `drain` for instant removal
from new-connection balancing: leaving maintenance triggers the configured
`slowstart` ramp, leaving drain does not.

Every server line the cookbook renders has `agent-check` when
`node['gitlab-haproxy']['agent']['enable']` is set, which it is in gstg,
gprd and pre. The exceptions are `asset_proxy` and `packhorse`, whose
templates write a single external server inline; nothing can drain those.

Each server sends its own row key first and then the groups it belongs to,
for example `agent-send "web/gke-cny-web canary\n"`. The agent answers with
the **first key that has an entry**, so a row key overrides a group key for
that one server, in either direction: `web/gke-cny-web = ready` next to
`canary = drain` keeps that row in rotation. Groups are defined per pool in
`node['gitlab-haproxy']['agent']['groups']` in the gitlab-haproxy cookbook;
today there is one, `canary`, covering the `canary_*` pools. Row keys always
contain a slash, group keys never do.

The agent's answer is applied on every 2s poll and its `ready` clears the
same admin flags as `set server ... state ready`. A state set over the local
unix socket lasts until the next poll. After a haproxy reload every server
starts `ready` and gets its KV state back within the first poll.

## Changing server state

**chatops is the supported way.** Release managers and on-call use it, it
records who did what in Slack, and it refuses to drain canary during a
canary deploy:

```
/chatops run canary --disable --gprd   # drain, wait 60s, maint
/chatops run canary --enable --gprd
```

It writes and deletes one key, `gitlab-haproxy-agent/state/canary`, on the
environment's consul at `consul-gl-internal.<env>.gke.gitlab.net:8500`, and
shows the KV state with any per-server overrides. It reads nothing from the
load balancers.

### Break glass: consul directly

When chatops is unavailable, or for a state chatops has no command for (a
single server, a weight), write the key yourself from a console node of the
environment (`console-01-sv-gprd`, `console-01-sv-gstg`, `console-01-sv-pre`),
which runs a consul agent joined to that environment's cluster. Any HAProxy
node works too. The whole canary set is the group key:

```shell
consul kv put gitlab-haproxy-agent/state/canary drain
consul kv put gitlab-haproxy-agent/state/canary maint
consul kv delete gitlab-haproxy-agent/state/canary        # ready
```

A single server is its `<backend>/<server>` row as named in `haproxy.cfg`.
A server that appears in several backends (`api-gke-us-east1-b` in `api` and
`main_api`, `kas-gke` in `kas`, `kas_grpc` and `kas_k8s_proxy`) has one row
per backend, and each row is its own key:

```shell
consul kv put gitlab-haproxy-agent/state/https_git/git-https-gke-us-east1-b drain
consul kv delete gitlab-haproxy-agent/state/https_git/git-https-gke-us-east1-b
```

To list the rows for a server, on any LB node:

```shell
echo "show stat" | sudo socat stdio /run/haproxy/admin.sock \
  | awk -F, '$2 == "git-https-gke-us-east1-b" {print $1"/"$2}'
```

or in Mimir: `count by (backend) (haproxy_server_status{server="git-https-gke-us-east1-b"})`.

Everything currently set, in any environment, is the prefix:

```shell
consul kv get -recurse gitlab-haproxy-agent/state/
```

An empty result means every server is `ready`.

Draining a server triggers [`HAProxyServerDown`](haproxy.md#server-down).

## Verifying

A drained row shows as `DRAIN (agent)` in `show stat`: the suffix means the
row has an agent check, which every row has. `MAINT` has no suffix.

```shell
echo "show stat" | sudo socat stdio /run/haproxy/admin.sock \
  | awk -F, '$2 ~ /-cny-/ {print $1"/"$2": "$18}'
```

What a specific agent answers, on the HAProxy node, with the same keys the
server line sends:

```shell
printf 'web/gke-cny-web canary\n' | nc 127.0.0.1 9777
```

Fleet-wide, in Mimir (`haproxy_server_status` comes from haproxy's built-in
exporter):

```promql
sum by (backend, server, state) (haproxy_server_status{server=~".*-cny-.*"} == 1)
```

## When something is off

- The agent serves `/-/liveness`, `/-/readiness` (503 until the first
  consul sync), `/-/metrics`, and `/debug/pprof/` on port 9778. Sync
  freshness, response latency, and error counters are in the metrics.
- If KV writes are not taking effect on a node, its consul watch is likely
  broken: see
  [HAProxyAgentConsulSyncStale](alerts/HAProxyAgentConsulSyncStale.md).
- The agent never guesses. When it is stale or down, haproxy keeps each
  server's last received state. A drain issued during that window needs to
  be confirmed or re-issued after recovery.
- Logs are in the `pubsub-system-inf-<env>` index (data stream, query as
  `.ds-pubsub-system-inf-<env>-*`) with `json.ident: gitlab-haproxy-agent`.
- If one node ignores KV for a backend that has a health-check port (the kas
  family, `pages_https`), check the port haproxy polls the agent on:
  `echo "show servers state <backend>" | sudo socat stdio /run/haproxy/admin.sock`,
  last column, must be `9777`. A wrong port came from the server state
  file, which is turned off everywhere now; the one-time fix is
  `echo "set server <backend>/<server> agent-port 9777" | sudo socat stdio /run/haproxy/admin.sock`.
  Background: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/work_items/29645#note_3769584388>
