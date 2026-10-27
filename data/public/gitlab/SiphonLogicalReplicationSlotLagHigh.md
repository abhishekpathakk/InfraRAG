# SiphonLogicalReplicationSlotLagHigh

## Overview

This alert fires when a Siphon logical replication slot on a GitLab.com
Patroni primary has more than 100 GiB of unconfirmed WAL. In other words,
Siphon's producer for the affected cluster is at least 100 GiB behind the
primary's current WAL position.

Siphon consumes PostgreSQL's WAL via logical replication slots named like
`prd_main_siphon_slot_1`, `prd_ci_siphon_slot_1`, `prd_sec_siphon_slot_1`
(or the `stg_*` equivalents on staging). Each slot tracks a consumer's
`confirmed_flush_lsn` — the LSN up to which Siphon has confirmed receiving
and persisting data. Until the slot advances past an LSN, PostgreSQL must
retain the WAL for it.

Contributing factors include:

- Siphon producer is crashed, scaled to zero, or stuck.
- NATS JetStream (Siphon's downstream) is unavailable, so the producer
  cannot publish events and therefore cannot acknowledge WAL.
- A very large transaction on the primary has produced a burst of WAL
  that Siphon cannot chew through fast enough.

Parts of the service affected:

- Directly: the Patroni primary whose fqdn is in the alert label set. WAL
  is accumulating on its data volume.
- Indirectly: GitLab.com itself — if WAL accumulation fills the Patroni
  primary's data volume, the database will stop accepting writes.

The recipient is expected to triage Siphon first (get the producer
caught up or stop it cleanly). Scaling the producer to 0 and then
back to 1 quickly may resolve the situation.

## Services

- [Siphon Service](../README.md)
- Team that owns the service:
  [Platform Insights](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/)
- Downstream of the [Patroni Service](../../patroni/README.md), whose
  disk is at risk when this alert fires.

## Metrics

- Metric: `pg_replication_slots_confirmed_flush_lsn_bytes`
- Unit: bytes
- Source: postgres_exporter on the Patroni primaries, scraped into the
  `gitlab-gprd` and `gitlab-gstg` Mimir tenants.
- Despite the name, this metric is emitted as the **delta** between the
  primary's current WAL LSN and the slot's `confirmed_flush_lsn` — i.e.
  it is equivalent to
  `pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)`. It rises
  as the consumer falls behind and falls as the consumer catches up.
- Threshold: 100 GiB (`100 * 1024 * 1024 * 1024` bytes), sustained for
  5 minutes. This threshold is a compromise between catching real
  problems early and not paging on transient backpressure. The Siphon
  runbook notes that mitigation is typically required within < 1 day,
  and GitLab.com Patroni primaries generate WAL at up to ~150 MB/s
  (see `PrimaryDatabaseWALGenerationSaturationSustainedOver150MBS`), so
  100 GiB corresponds to roughly 10–15 minutes of unconsumed WAL at
  saturation — well before disk retention becomes a concern.
- Normal behaviour: the metric hovers in the low MB to single-digit GB
  range for healthy slots, oscillating as the consumer catches up. A
  sustained upward trend is the typical failure mode and the signal
  this alert is tuned to catch.

## Alert Behavior

- This alert clears automatically once the slot catches up below the
  100 GiB threshold.
- Silencing is only appropriate during an open Change Request for
  Siphon or the affected Patroni cluster, or when a re-snapshot is
  deliberately in progress.
- This should be a rare alert. Under normal operation, Siphon keeps
  well under the threshold. A firing alert almost always indicates a
  producer outage.
- **Automatic safeguard:** GitLab.com Patroni clusters are configured
  with `max_slot_wal_keep_size` so PostgreSQL will invalidate a slot
  that retains more than the configured amount of WAL, rather than
  let the primary run out of disk. This alert is tuned to fire well
  before that limit, so that a human can catch up or cleanly stop the
  producer without forcing a full Siphon re-snapshot. See
  [database-team/meetings#26 (comment 3271711718)](https://gitlab.com/gitlab-org/database-team/meetings/-/issues/26#note_3271711718).
- [Previous incidents tagged with this alert](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&search=SiphonLogicalReplicationSlotLagHigh)

## Severities

- Default severity: `s2`, `pager: pagerduty`. This alert pages because
  unchecked lag on a Siphon slot can exhaust disk on a GitLab.com
  Patroni primary, which would compromise production.
- Direct impact at firing time is usually limited to Siphon's
  downstream consumers (ClickHouse-backed analytics). The severity
  reflects the risk of escalation to a primary-database outage, not
  the immediate customer impact.
- **Escalate to `s1`** if any of the following are true:
  - The Patroni primary's data volume utilisation is above 70% and
    trending upward — disk exhaustion on the primary is imminent and
    customer-wide.
  - `PrimaryDatabaseWALGenerationSaturationSustainedOver150MBS` is
    also firing on the same cluster — WAL is being generated faster
    than Siphon can ever catch up.
  - The slot has been lagging and growing for more than several
    hours with no sign of progress.

## Verification

- [Prometheus query (gprd)](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22one%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22max%28pg_replication_slots_confirmed_flush_lsn_bytes%7Bslot_type%3D%5C%22logical%5C%22%2C%20slot_name%3D~%5C%22.%2Asiphon.%2A%5C%22%7D%20and%20on%28instance%29%20pg_replication_is_replica%3D%3D0%29%20by%20%28fqdn%2C%20slot_type%2C%20slot_name%29%22,%22range%22:true,%22instant%22:false%7D%5D,%22range%22:%7B%22from%22:%22now-6h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Siphon Grafana folder](https://dashboards.gitlab.net/dashboards/f/cfj21k0em8cn4c/siphon)
- Kibana logs:
  - Production: [log.gprd.gitlab.net](https://log.gprd.gitlab.net/app/r/s/6LMBY)
  - Staging: [nonprod-log.gitlab.net](https://nonprod-log.gitlab.net/app/r/s/qLnJb)

You can also verify the lag and the active session holding the slot
directly on the primary:

```sql
SELECT
  slot_name,
  active,
  active_pid,
  pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes
FROM pg_replication_slots
WHERE slot_type = 'logical' AND slot_name ILIKE '%siphon%';
```

## Recent changes

- [Recent Siphon changes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=updated_desc&state=opened&label_name%5B%5D=Service%3A%3ASiphon)
- [Recent Patroni changes](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=updated_desc&state=opened&or%5Blabel_name%5D%5B%5D=Service%3A%3APatroni&or%5Blabel_name%5D%5B%5D=Service%3A%3APatroniCI&or%5Blabel_name%5D%5B%5D=Service%3A%3APatroniSec)
- Roll back Siphon producer deployments via the usual Kubernetes
  rollback on the `orbit-prd` / `orbit-stg` cluster in the `siphon`
  namespace.

## Troubleshooting

Full triage steps live in the Siphon runbook under
[High logical replication lag / producer not running](../README.md#high-logical-replication-lag--producer-not-running).
The recommended order of operations is:

1. **Identify the affected DB cluster.** The `slot_name` label in the
   alert encodes it (e.g. `prd_main_siphon_slot_1` → `main`,
   `prd_ci_siphon_slot_1` → `ci`, `prd_sec_siphon_slot_1` → `sec`).
2. **Check NATS JetStream health.** If NATS is down, Siphon cannot
   publish and lag will grow. See the
   [NATS runbook](../../nats/README.md).
3. **Check the Siphon producer pods** on the relevant `orbit-*`
   cluster:

   ```shell
   glsh kube use-cluster orbit-prd --no-proxy
   kubectl get pods -n siphon -o wide
   kubectl logs -n siphon -l app=postgres-producer-<db> --tail=200
   ```

4. **Try bouncing the producer.** Scaling the deployment to 0 and
   then back to 1 quickly often unsticks a wedged producer:

   ```shell
   kubectl scale deployment postgres-producer-<db> --replicas=0 -n siphon
   kubectl scale deployment postgres-producer-<db> --replicas=1 -n siphon
   ```

5. **If bouncing doesn't help, disconnect the active session holding
   the slot on the primary.** This forces the producer to reconnect
   and can clear stuck replication state. First find the PID:

   ```sql
   SELECT
     slot_name,
     active_pid,
     pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn)) AS lag_bytes
   FROM pg_replication_slots
   WHERE slot_type = 'logical' AND slot_name ILIKE '%siphon%';
   ```

   Then terminate the `active_pid` if present:

   ```sql
   SELECT pg_terminate_backend(<active_pid>);
   ```

Additional dashboards:

- [Patroni primary saturation dashboard](https://dashboards.gitlab.net/d/alerts-sat_pg_xlog_position_bytes)
  — check WAL generation rate on the affected cluster.
- [Patroni disk utilisation](https://dashboards.gitlab.net/d/patroni-main/patroni-overview)
  — check how much headroom you have before disk exhaustion.

## Possible Resolutions

- No prior incidents recorded yet; this alert is new. Add links here
  as we accumulate production experience.
- [All previous incidents involving Siphon](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3ASiphon)

## Dependencies

- Siphon producer (`postgres-producer-*` pods in the `siphon`
  namespace).
- NATS JetStream — Siphon's pub/sub layer.
- Patroni primary of the affected cluster (`patroni`, `patroni-ci`,
  or `patroni-sec`) — the host PostgreSQL that owns the slot.

## Escalation

- Primary contact: `#g_analytics_platform_insights` Slack channel
  ([team handbook](https://handbook.gitlab.com/handbook/engineering/data-engineering/analytics/platform-insights/)).
  Individuals with the most context: `@ahegyi`, `@arun.sori`,
  `@ankitbhatnagar`.
- For immediate emergencies, or if there is no response from the
  primary contacts, escalate to `#database_operations` — database
  reliability can step in to prevent disk exhaustion on the Patroni
  primary.

## Definitions

- [Alert definition (Jsonnet source)](../../../libsonnet/alerts/siphon-replication-lag-alerts.libsonnet)
- [Generator wiring](../../../mimir-rules-jsonnet/siphon-replication-lag-alerts.jsonnet)
- The tunable parameters are the 100 GiB threshold and the 5-minute
  `for:` window. Raise the threshold if we accumulate data showing
  steady-state lag regularly exceeds it under healthy operation;
  lower it if we find disk-exhaustion incidents occurring before it
  fires.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/siphon/alerts/SiphonLogicalReplicationSlotLagHigh.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related Siphon alerts](./)
- [Siphon service overview](../README.md)
- [Patroni service overview](../../patroni/README.md)
- [PrimaryDatabaseWALGenerationSaturationSustainedOver150MBS runbook](../../patroni/primary_db_node_wal_generation_saturation.md)
- [Unhealthy Patroni node handling](../../patroni/unhealthy_patroni_node_handling.md)
