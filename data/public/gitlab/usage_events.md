# Troubleshooting Hosted Runners Usage Events

These alerts monitor the internal billing-event delivery pipeline from GitLab
Runner to the Data Insights Platform (DIP). They page for billing-pipeline
problems and do not contribute to Runner service SLIs, SLOs, or error budgets.

## Alerts

| Alert | Meaning |
| --- | --- |
| `HostedRunnersUsageEventsDropped` | Events were dropped from the in-memory queue because it overflowed. |
| `HostedRunnersUsageEventsDeliveryFailing` | Event-send attempts have been failing persistently. Retries count as additional attempts. |
| `HostedRunnersUsageEventsQueueNearCapacity` | The storage queue is approaching capacity and buffered events are at risk. |

## Investigation

1. Identify the tenant and the affected `stack`, `shard`, and `runner_manager`
   from the notification. Record the incident time range.
2. Open **Hosted Runners Overview** in the tenant's Grafana. Select the affected
   stack, shard, and manager, then inspect **Runner Manager Usage Events**.
3. Compare failed and successful deliveries, queue depth and capacity, and
   overflow drops. Determine whether the problem affects one manager or
   multiple stacks or tenants.
4. Inspect Runner logs for usage-event delivery errors. Check the configured
   collector endpoint, DNS and network connectivity, and collector authentication,
   including IAM/OIDC errors where applicable.
5. Open or update an incident through the Dedicated incident workflow. Record
   the impact as delayed billing events, observed queue drops, or both.
   Coordinate collector-side investigation with DIP responders and data-loss
   assessment with the billing team.

Events are buffered in memory. Preserve relevant logs and metrics, and consider
the buffered events before restarting or replacing an affected manager.

## Recovery

- Confirm successful deliveries resume, delivery failures subside, and the
  queue drains.
- Confirm the overflow-drop counter stops increasing.
- If drops occurred, document the affected period and assess recovery or
  reconciliation options with the billing team.

An alert resolving only means its condition no longer matches. In particular,
the drop alert resolves when observed drops leave its configured lookback;
this does not establish that missing events were recovered or billing reconciled.

## Coverage and follow-up

The alerts are included by default. Absent usage-event metrics, or an idle
emitter with zero counters and an empty queue, do not trigger them.

**Deferred:** detecting missing emission when usage events should be generated.
There is currently no metric identifying managers where usage events are
configured and expected. Add that signal in GitLab Runner, then design a
separate check that also accounts for whether event-producing work occurred.

These alerts monitor Runner-side delivery and queue health. Successful delivery
to the collector does not by itself confirm downstream billing completion.
