# Growth – Trials Health Runbook

This runbook covers four Prometheus alerts that monitor the GitLab trial
provisioning pipeline end-to-end: SaaS trial creation, SM trial activation,
and the Workato lead handoff to Marketo/CRM.

> **Note:** This is a suite runbook covering four related alerts.
> All alerts are defined in
> `mimir-rules/gitlab-gprd/growth/growth-trials-health.yml`
> and route to `#g_growth_trials_alerts`.

---

## Overview

These alerts fire when GitLab trial provisioning degrades in production (`gprd`).
The pipeline spans two services:

- **CustomersDot** (`gitlab-subscriptions-prod`) handles trial creation requests
  from GitLab.com, SM activation via `cloudActivationActivate`, and the Workato
  lead handoff via `Workato::CreateLeadJob`.
- **GitLab.com Rails** handles SaaS trial registration and Aha D14 activation
  tracking.

Failures here mean potential customers cannot start trials, which directly
affects Growth team OKRs and revenue pipeline.

## Services

- [CustomersDot service overview](https://dashboards.gitlab.net/d/customersdot-main)
- [Growth – Trials Health dashboard](https://dashboards.gitlab.net/d/growth-trials-health)
- **Team:** Growth / Monetization — `#g_growth` on Slack
- **Alerts channel:** `#g_growth_trials_alerts`
- **CustomersDot oncall/incidents:** `#f_customersdot`

## Metrics

| Metric prefix | Source | Baseline (gprd) |
| --- | --- | --- |
| `growth_trial_creation_*` | GCP log-based metric, CustomersDot | ~10K+/week (~1.67/min) |
| `growth_sm_trial_activation_*` | GCP log-based metric, `cloudActivationActivate` | ~100–123/week (~0.015/min) |
| `growth_workato_lead_*` | GCP log-based metric, Sidekiq Workato jobs | Proportional to trial creation |
| `growth_marketo_inbound_*` | GCP log-based metric, `/marketo_trial` endpoint | Low volume |
| `growth_trial_activation_aha14_*` | App-level LabKit counter, GitLab.com Rails | Subset of SaaS trials |
| `growth_sm_trial_activation_duration_seconds` | GCP log-based distribution metric, `jsonPayload.duration_s` | Trial-only request latency via lograge |
| `growth_trial_provision_latency_seconds_bucket` | App-level LabKit histogram, GitLab.com Rails (#968) | Preferred long-term; covers SaaS trial latency |

Thresholds are anchored to the baselines above. Failure rates are expected to be
near zero in normal operation; alert thresholds represent a meaningful signal
above noise rather than a percentage of traffic.

If metrics stop appearing in Grafana, check the GCP → Cloud Monitoring → OTEL →
Mimir pipeline before assuming the underlying service is healthy. See
the GrowthTrialCreationNearZero investigation step 4 below.

### Critical filter: `source_class_name="Trial"`

The `growth_sm_trial_activation_*` metrics and the
`growth_sm_trial_activation_duration_seconds` latency distribution **must** use
`jsonPayload.source_class_name="Trial"` as a filter in their Cloud Logging metric
definitions. Without it, the counters include subscription activations
(`cloudActivationActivate` handles both), which inflates baselines and renders
alert thresholds meaningless.

This field is set via `SafeRequestStore` by `CloudActivations::ActivateService#execute`
and is present in both the lograge request log and service-level log lines.
It was added in
[customers-gitlab-com!15060](https://gitlab.com/gitlab-org/customers-gitlab-com/-/merge_requests/15060),
which also enables separate latency profiling of the trial vs. subscription
activation paths.

> **If this field is ever renamed or removed from CustomersDot**, the GCP log-based
> metric filters will silently start counting all activations. Update the Cloud
> Logging metric filter expressions in `gitlab-subscriptions-prod` and re-validate
> baselines before re-enabling alerts.

## Alert Behavior

| Alert | Severity | Condition | For | Expected frequency |
| --- | --- | --- | --- | --- |
| GrowthTrialCreationFailureSpike | s3 | failure rate > 0.5/5m | 10m | Rare; spikes during bad deploys |
| GrowthSMTrialActivationFailure | s3 | failure rate > 0.1/5m | 5m | Rare; near-zero baseline |
| GrowthTrialCreationNearZero | s2 | success rate < 0.01/s | 15m | Should almost never fire |
| GrowthWorkatoLeadErrors | s4 | error rate > 0.05/5m | 10m | Occasional; Workato API instability |

Silencing: alerts can be silenced in Alertmanager during planned CustomersDot
maintenance windows or when a known incident is already being worked.

## Severities

- **s2 (GrowthTrialCreationNearZero):** Trial creation has effectively stopped.
  Create an incident immediately. Page `@growth-oncall` if outside business hours.
  All customers attempting to start a GitLab.com trial are affected.

- **s3 (GrowthTrialCreationFailureSpike, GrowthSMTrialActivationFailure):**
  Elevated failure rate but not a total outage. Triage within 30 minutes during
  business hours. Create an incident if the rate is still climbing or if more than
  ~50 failures have accumulated. SM activation failures affect paying SM customers
  trying to activate trial licenses.

- **s4 (GrowthWorkatoLeadErrors):** Trial creation is unaffected; only CRM/Marketo
  data is impacted. Investigate within the business day. No incident required unless
  data loss is significant and unrecoverable.

## Recent changes

When an alert fires, check for recent changes that may have caused it:

- [CustomersDot recent deployments](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=merged&label_name[]=Service%3A%3ACustomersDot)
  — look for merges in the last 2 hours
- [gitlab-org/customers-gitlab-com recent MRs](https://gitlab.com/gitlab-org/customers-gitlab-com/-/merge_requests?scope=all&state=merged)
- [GitLab.com recent deployments](https://dashboards.gitlab.net/d/general-deployment-home)
  — for GrowthTrialCreationNearZero when CustomersDot is healthy

## Dependencies

The trial provisioning pipeline depends on all of the following:

| Dependency | Type | Failure symptom |
| --- | --- | --- |
| CustomersDot Rails app (`gitlab-subscriptions-prod`) | Internal | All alerts |
| GCP log-based metrics pipeline (Cloud Monitoring → OTEL → Mimir) | Internal | Metrics absent; NearZero false-positive |
| `cloud_activation_key` service | Internal | SM activation failures |
| Workato API | External | GrowthWorkatoLeadErrors only |
| Marketo API | External | Downstream of Workato; silent until Workato fails |
| GitLab.com Rails (`gprd`) | Internal | SaaS trial creation failures |

---

## Alerts

### GrowthTrialCreationFailureSpike

**Severity:** s3
**Condition:** `growth_trial_creation_failure_total` rate > 0.5/5m for 10 minutes.

**What it means:** CustomersDot is failing to provision SaaS trials at an elevated
rate. The baseline failure rate is near zero; 0.5/5m represents a meaningful spike.

**Investigation steps:**

1. Open the dashboard panel:
   [Growth – Trials Health → Trial creation failure rate](https://dashboards.gitlab.net/d/growth-trials-health?var-environment=gprd&var-deployment_type=saas)

2. Check GCP Logs Explorer for CustomersDot errors:

   ```
   resource.type="gce_instance"
   logName="projects/gitlab-subscriptions-prod/logs/rails.production"
   jsonPayload.type="customersdot"
   jsonPayload.severity="ERROR"
   ```

   Project: `gitlab-subscriptions-prod`

3. Check Kibana for TrialsController errors:
   Index: `pubsub-rails-inf-gprd*`
   Filter: `json.controller: "TrialsController" AND json.status >= 500 AND json.environment: "production"`

4. Check CustomersDot incident history and recent deploys in `#f_customersdot`.

5. If the spike correlates with a deploy, consider reverting via the standard
   CustomersDot rollback process.

**Resolution:** Alert auto-resolves when the rate drops below 0.5/5m.

**Possible resolutions:** No past incidents documented yet. Add links here after
the first real firing.

---

### GrowthSMTrialActivationFailure

**Severity:** s3
**Condition:** `growth_sm_trial_activation_failure_total` rate > 0.1/5m for 5 minutes.

**What it means:** Self-managed trial activations via `cloudActivationActivate` are
failing. Baseline is near zero (~100–123 SM activations/week in gprd). Any sustained
failures are notable and affect SM customers trying to activate trials.

**Investigation steps:**

1. Open the dashboard panel:
   [Growth – Trials Health → SM trial activation failure rate](https://dashboards.gitlab.net/d/growth-trials-health?var-environment=gprd&var-deployment_type=self_managed)

2. Check GCP Logs Explorer for SM activation failures:

   ```
   resource.type="gce_instance"
   logName="projects/gitlab-subscriptions-prod/logs/rails.production"
   jsonPayload.message="Trial creation failed"
   ```

   For a full request trace, find the `correlation_id` from a failure entry, then:

   ```
   resource.type="gce_instance"
   logName="projects/gitlab-subscriptions-prod/logs/rails.production"
   jsonPayload.correlation_id="<correlation_id>"
   ```

   Source class: `Trials::SelfManaged::BaseService` (failure) and
   `CloudActivations::ActivateService` (activation errors like expired trial,
   feature flag disabled, incompatible GitLab version).

3. Verify CustomersDot is healthy (check `#f_customersdot` for recent incidents).

4. Check if the `cloud_activation_key` service or any upstream dependency is degraded.

**Resolution:** Alert auto-resolves when the rate drops below 0.1/5m.

**Possible resolutions:** No past incidents documented yet. Add links here after
the first real firing.

---

### GrowthTrialCreationNearZero

**Severity:** s2
**Condition:** `growth_trial_creation_success_total` rate < 0.01/s for 15 minutes
while the metric series is present.

**What it means:** The trial creation pipeline appears to have stopped processing
successful trials entirely. Expected baseline in gprd is ~1.67/min (~10K+/week).
This suggests a complete outage of trial provisioning.

**Investigation steps:**

1. Open the dashboard panel:
   [Growth – Trials Health → Trial creation success rate](https://dashboards.gitlab.net/d/growth-trials-health?var-environment=gprd)

2. Verify CustomersDot is up and responding — check the CustomersDot service
   health dashboard and `#f_customersdot`.

3. Check GCP Logs Explorer for any CustomersDot application errors:

   ```
   resource.type="gce_instance"
   logName="projects/gitlab-subscriptions-prod/logs/rails.production"
   jsonPayload.type="customersdot"
   jsonPayload.severity="ERROR"
   ```

   Project: `gitlab-subscriptions-prod`

4. Confirm the GCP log-based metric is still being exported — check Cloud
   Monitoring metric explorer for `custom.googleapis.com/growth_trial_creation_*`.
   If absent, the metric pipeline (GCP → OTEL → Mimir) may be broken rather
   than the trial service itself. Contact `#g_observability`.

5. If CustomersDot is healthy and metrics are flowing, check GitLab.com Rails
   for errors at the trial registration endpoint (`/trials`).

**Resolution:** Alert auto-resolves when the rate rises above 0.01/s.

**Possible resolutions:** No past incidents documented yet. Add links here after
the first real firing.

---

### GrowthWorkatoLeadErrors

**Severity:** s4
**Condition:** `growth_workato_lead_error_total` rate > 0.05/5m for 10 minutes.

**What it means:** The `Workato::CreateLeadJob` Sidekiq worker is failing to hand
off trial leads to Workato / Marketo. This does **not** block trial creation for
the end user but affects CRM / marketing data quality.

**Investigation steps:**

1. Open the dashboard panel:
   [Growth – Trials Health → Workato lead handoff error rate](https://dashboards.gitlab.net/d/growth-trials-health)

2. Check Kibana for Workato job errors:
   Index: `pubsub-sidekiq-inf-gprd*`
   Filter: `json.class: "Workato::CreateLeadJob" AND json.job_status: "fail"`

3. Check if Workato's API endpoint is responding — ask in `#g_growth` for a
   Workato status check.

4. Sidekiq dead queue: check whether `Workato::CreateLeadJob` jobs are piling
   up in the dead queue in `#f_customersdot` or the CustomersDot Sidekiq dashboard.

**Resolution:** Alert auto-resolves when the rate drops below 0.05/5m.

**Possible resolutions:** No past incidents documented yet. Add links here after
the first real firing.

---

## Escalation

| Scenario | Action |
| --- | --- |
| s2 alert (NearZero), business hours | Triage immediately; post in `#g_growth_trials_alerts` and `#g_growth` |
| s2 alert, outside business hours | Page `@growth-oncall`; if unresponsive after 15 min, escalate to engineering manager |
| s3 alert, business hours | Triage within 30 min; post update in `#g_growth_trials_alerts` |
| s3 alert, outside business hours | Triage next business morning unless rate is still climbing |
| s4 alert | Investigate within the business day; no page required |
| CustomersDot incident | Coordinate in `#f_customersdot` |
| Metrics pipeline broken | Contact `#g_observability` |

## Saved investigation queries

### GCP Logs Explorer

**All CustomersDot errors (last 30 min):**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.type="customersdot"
jsonPayload.severity="ERROR"
```

Project: `gitlab-subscriptions-prod`

**SM activation — successful activations only:**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.message="Instance successfully cloud activated"
jsonPayload.source_class_name="Trial"
```

Source: `CloudActivations::ActivateService#activate_instance` (Gitlab::Logger)
`source_class_name="Trial"` scopes to trial activations (vs subscription activations).

**SM activation — trial creation failures:**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.message="Trial creation failed"
```

Source: `Trials::SelfManaged::BaseService#execute` (Gitlab::Logger)

**SM activation — all trial activation requests (request-level):**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.params.value=~"cloudActivationActivate"
jsonPayload.source_class_name="Trial"
```

Source: lograge request log. `source_class_name` is set via `SafeRequestStore`
by `CloudActivations::ActivateService#execute` — null means it's a subscription
activation, not a trial. Use `jsonPayload.correlation_id` to find companion
service log lines for a specific request.

**SM activation — trial request latency (slow activations):**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.params.value=~"cloudActivationActivate"
jsonPayload.source_class_name="Trial"
jsonPayload.duration_s > 5
```

The `jsonPayload.duration_s` field (lograge) is the source for the
`growth_sm_trial_activation_duration_seconds` distribution metric. Use this query
to spot-check slow individual requests during a latency regression. Prior to
[customers-gitlab-com!15060](https://gitlab.com/gitlab-org/customers-gitlab-com/-/merge_requests/15060),
`source_class_name` was absent and trial/subscription latencies could not be
separated from this log.

**Trace a specific activation by correlation_id:**

```
resource.type="gce_instance"
logName="projects/gitlab-subscriptions-prod/logs/rails.production"
jsonPayload.correlation_id="<paste correlation_id here>"
```

**Note on "Trial cloud activation creation successful":** This message comes from
`Trials::SelfManaged::CreateUltimateTrialService#after_trial_creation_actions` and
fires only when the `CloudActivation` database record is persisted — it's a sub-step,
not the instance activation itself. If absent from logs, check whether
`trial.create_cloud_activation` is returning a non-persisted record.

### Kibana

**TrialsController errors (Rails):**

```
json.controller: "TrialsController" AND json.status >= 500 AND json.environment: "production"
```

Index: `pubsub-rails-inf-gprd*`

**Workato::CreateLeadJob failures:**

```
json.class: "Workato::CreateLeadJob" AND json.job_status: "fail"
```

Index: `pubsub-sidekiq-inf-gprd*`

---

## Definitions

- [Alert rule definitions](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/growth/growth-trials-health.yml)
- [Edit this runbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/growth/growth-trials-health.md)
- [Alert playbook template](../template-alert-playbook.md)

## Related Links

- [Growth – Trials Health dashboard](https://dashboards.gitlab.net/d/growth-trials-health)
- [Growth Error Budget](https://dashboards.gitlab.net/d/stage-groups-growth)
- [CustomersDot Overview](https://dashboards.gitlab.net/d/customersdot-main)
- [Growth team handbook](https://handbook.gitlab.com/handbook/marketing/growth/)
- [gitlab-org/growth/team-tasks#958](https://gitlab.com/gitlab-org/growth/team-tasks/-/work_items/958) — parent observability issue
