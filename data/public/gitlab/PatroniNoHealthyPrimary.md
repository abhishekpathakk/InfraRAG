# PatroniNoHealthyPrimary

## Overview

No node in the cluster has passed the Consul health check for the `<type>-master` service for 2
minutes. Clients find the primary through this service, so new connections have nowhere to go.

A normal automatic failover finishes well inside 2 minutes, so if this alert fires, **automatic
failover hasn't worked**. Treat the old primary as half-dead
([INC-14518](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/23026)) until you've
proved it isn't writing. Consul may have marked the node failed while its Postgres still commits on
connections it already holds. A stalled node can hang new connections while existing ones keep
writing, so "I can't connect" doesn't mean "it's gone".

**Do not fail over** until the runbook below has shown that the old primary's WAL position isn't
moving. A failover discards every write that only the old primary has.

## First steps

1. From a healthy member, check whether there is a Leader: `sudo gitlab-patronictl list`.
2. Follow [Primary unresponsive or no Leader: recover it without losing data](../primary-unresponsive-assess-before-failover.md).
   Its Step 2 tells the two states apart in a few minutes, starting with checks 0 (Consul), 2
   (is the primary still writing?) and 5 (is Patroni half-dead?).

## Why this signal

The value comes from the Consul servers, through consul_exporter, so it keeps working when the
primary's own exporters are down. On Sep 24 they were down for the whole incident, and the only page
was `PatroniScrapeFailures`. Consul marked the primary failed at 22:48:45, so this alert would have
fired at about 22:51. The database failure was confirmed at 23:13.

## Alert behaviour

- `for: 2m`: a switchover, or a successful automatic failover (lock TTL of up to 90 s plus
  promotion), normally clears before it fires.
- Clears as soon as one node passes the check.
- **Expected while you follow the [recovery runbook](../primary-unresponsive-assess-before-failover.md).**
  The `/master` check passes only on the node that holds the leader lock, and pausing doesn't change
  that, so the alert stays on while the paused cluster has no Leader. Acknowledge it rather than
  silencing it. It clears at "Confirm it's Leader on the same timeline" in
  [Step 3](../primary-unresponsive-assess-before-failover.md#step-3-recover-the-old-primary-in-place),
  once the old primary is Leader again and **before** you resume. If it's still firing, there is no
  Leader: don't resume.
- Silence it only for an approved change that deliberately leaves the cluster without a primary.
- Opposite condition: `PatroniConsulMultipleMaster` (more than one primary registered).
- Often fires together with [PatroniNoReplicaStreaming](PatroniNoReplicaStreaming.md).
- **Clearing doesn't mean it's safe.** If a replica is promoted while the old primary is half-dead,
  this alert clears, and so does PatroniNoReplicaStreaming, but the old primary can keep committing
  through existing PgBouncer server connections: a split brain. `PostgresSplitBrain` can't see it
  while the old primary's `postgres_exporter` is down. After any failover, confirm the old primary
  is fenced (VM stopped, or its WAL position not moving).
- Not covered: Postgres crashing on a primary that still holds the leader lock. `/master` follows
  the lock, not Postgres, so the check keeps passing until Patroni releases it.

## Escalation

This is an outage for the cluster. Declare an incident, and escalate to the DBO (Database Operations)
on-call with `/incident escalate` in the incident channel
([manual escalation](../../incident-io/oncall.md#manual-escalation)).

## Related links

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/alerts/patroni-leadership-alerts.libsonnet)
- [Link to edit this playbook](PatroniNoHealthyPrimary.md)
- [Patroni management](../patroni-management.md)
