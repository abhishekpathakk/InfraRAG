# DuoWorkflowSvcServiceCheckpointErrorsErrorSLOViolation

## Overview

- This alert fires when the error rate of checkpoint operations exceeds the SLO threshold.
- A checkpoint is the state of a LangGraph graph at a particulat point in time. They are critical for workflow persistence and recovery.
- Duo Workflow Service makes HTTP requests to Rails API (/api/v4/ai/duo_workflows/workflows/:id/checkpoints) to fetch / save checkpoints. They are stored in the Postgres DB.
- This alert indicates that the checkpoint system is experiencing higher-than-acceptable failure rates.
- Possible user impacts
  - Agentic chat loses context from previous messages eg it won't remember previous messages.
  - Users cannot resume software development sessions after a pause event such as tool call approval, user input, etc.
  - Users cannot resume older sessions.

## Services

- [Duo Workflow Service overview](../README.md)
- Rails
- Team that owns the service: [Agent Foundations](https://handbook.gitlab.com/handbook/engineering/ai/agent-foundations)

## Metrics

- The metric used is `gitlab_component_errors:confidence:ratio_1h` and `gitlab_component_errors:confidence:ratio_6h` for the `checkpoint_errors` component of `duo-workflow-svc`.
- This metric measures the error rate of checkpoint operations (4xx and 5xx errors), expressed as a percentage (0-100%).
- The SLO threshold is 5% error rate, meaning the alert fires when errors exceed this threshold.
- [Link to metric catalogue](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/duo-workflow-svc.jsonnet)

## Alert Behavior

- To silence the alert, please visit [Alert Manager Dashboard](https://alerts.gitlab.net/#/alerts?silenced=false&inhibited=false&active=true&filter=%7Balertname%3D%22DuoWorkflowSvcServiceCheckpointErrorsErrorSLOViolation%22%7D)
- This alert is expected to be rare under normal conditions. High frequency indicates checkpoint storage or persistence issues.

## Severities

- This alert creates S2 incidents (High severity, pages on-call).
- All gitlab.com, self-managed and dedicated customers (other than those using self-hosted DAP) using Duo Workflow features are potentially impacted, especially long-running workflows.
- Review [Incident Severity Handbook](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/#incident-severity) page to identify the required Severity Level.

## Verification

- [Prometheus link to query that triggered the alert](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22pum%22:%7B%22datasource%22:%22mimir-runway%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22gitlab_component_errors:confidence:ratio_1h%7Bcomponent%3D%5C%22checkpoint_errors%5C%22,monitor%3D%5C%22global%5C%22,type%3D%5C%22duo-workflow-svc%5C%22%7D%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-runway%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Duo Workflow Service Overview Dashboard](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview?orgId=1)
- See "SLI Detail: checkpoint_errors" section in the Duo Workflow Service Overview Dashboard for further information.
- See [Rails logs](https://log.gprd.gitlab.net/app/r/s/MJJ5n) for the checkpoints endpoints (/api/v4/ai/duo_workflows/workflows/:id/checkpoints)

## Recent changes

- [Recent Duo Workflow Service Production Changes](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/pipelines?page=1&scope=all&ref=main)
- Since the error could be originated from GitLab REST API, see also recent changes in the GitLab repository, specifically [this endpoint](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/api/ai/duo_workflows/workflows_internal.rb#L127).

## Troubleshooting

1. **See checkpoint endpoint logs:**
   - Visit <https://log.gprd.gitlab.net/app/r/s/VCMrK> or filter by `json.path : *checkpoints` in Rails logs in Kibana.
   - Check the json.status field to see what is the http status code.

2. **Check duo workflow service logs:**
   - Get session IDs from the step 1. You can see the id in the `json.path`.
   - Go to [runway logs for duo workflow service](https://cloudlogging.app.goo.gl/PuutesjcPCF9tBTn7) and filter by `jsonPayload.workflow_id`

3. **Check for recent changes:**
   - Review recent changes mentioned under Recent changes section.
   - Check if a recent deployment affected checkpoint handling.
   - If a recent change caused the issue, consider rolling back.

## Possible Resolutions

- N.A. We don't have historical data on this alert's resolutions.

## Dependencies

- GitLab Rails + Postgres DB
- Workhorse
- AI Gateway / Duo Workflow Service

## Escalation

- For investigation and resolution assistance, escalate to the `tier2 - AI` on-call rotation.
  Use `/inc escalate` in Slack and select `tier2 - AI` from the "Oncall team" dropdown (see
  [How to Escalate](https://gitlab.com/gitlab-com/runbooks/-/tree/master/on-call#how-to-escalate)).

## Definitions

- [Review the alert here](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/runway/duo-workflow-svc/autogenerated-runway-duo-workflow-svc-service-level-alerts.yml)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Duo Agent Platform Architecture](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/duo_workflow/)
- [Related alerts](./)
- [Duo Workflow Service Runbook docs](../README.md)
