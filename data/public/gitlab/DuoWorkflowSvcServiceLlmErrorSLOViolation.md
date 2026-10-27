# DuoWorkflowSvcServiceLlmErrorSLOViolation

## Overview

- This alert fires when the error rate of LLM inference requests exceeds the SLO threshold.
- LLM failures indicate that requests to the LLM provider is failing.
- This alert indicates that we're experiencing higher-than-acceptable request failure rates.
- The root cause can be due to invalid input, too large payload, or an issue with the LLM provider (overloaded, etc).
- Possible user impacts
  - Users will see errors like 'There was an error connecting to the chosen LLM provider, please try again or contact support if the issue persists.' or 'There was an error processing your request in the Duo Agent Platform, please try again or contact support if the issue persists.'
  - It's possible that these errors will be isolated for an LLM provider or a specific model.

## Services

- [Duo Workflow Service overview](../README.md)
- Team that owns the service: [Agent Foundations](https://handbook.gitlab.com/handbook/engineering/ai/agent-foundations)

## Metrics

- The metric used is `gitlab_component_errors:confidence:ratio_1h` and `gitlab_component_errors:confidence:ratio_6h` for the `llm` component of `duo-workflow-svc`.
- This metric measures the error rate of LLM inference requests, expressed as a percentage (0-100%).
- The SLO threshold is 1% error rate, meaning the alert fires when errors exceed this threshold.
- [Link to metric catalogue](https://gitlab.com/gitlab-com/runbooks/-/blob/master/metrics-catalog/services/duo-workflow-svc.jsonnet)

## Alert Behavior

- To silence the alert, please visit [Alert Manager Dashboard](https://alerts.gitlab.net/#/alerts?silenced=false&inhibited=false&active=true&filter=%7Balertname%3D%22DuoWorkflowSvcServiceLlmErrorSLOViolation%22%7D)
- This alert is expected to be rare under normal conditions. High frequency indicates a problem with the payload we send to the LLM provider or issues with the LLM provider itself.
- The following reasons can be causing this alert
  - The LLM provider is experiencing issues or an outage
  - The request is invalid (eg. tool call is not followed by a tool result)
  - The requests are failing due to authentication
  - The payload is over the token limit of the LLM provider

## Severities

- This alert creates S2 incidents (High severity, pages on-call).
- All gitlab.com, self-managed and dedicated customers (other than those using self-hosted DAP) using Duo Workflow features are potentially impacted.
- Review [Incident Severity Handbook](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/#incident-severity) page to identify the required Severity Level.

## Verification

- [Prometheus link to query that triggered the alert](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22pum%22:%7B%22datasource%22:%22mimir-runway%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22gitlab_component_errors:confidence:ratio_1h%7Bcomponent%3D%5C%22llm%5C%22,monitor%3D%5C%22global%5C%22,type%3D%5C%22duo-workflow-svc%5C%22%7D%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-runway%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)
- [Duo Workflow Service Overview Dashboard](https://dashboards.gitlab.net/d/duo-workflow-svc-main/duo-workflow-svc-overview?orgId=1)
- See "SLI Detail: llm" section in the Duo Workflow Service Overview Dashboard for further information.

## Recent changes

- [Recent Duo Workflow Service Production Changes](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/pipelines?page=1&scope=all&ref=main)

## Troubleshooting

1. **Identify the source of LLM errors:**
   - Check if there are bad request errors in [DWS logs](https://cloudlogging.app.goo.gl/7wKTaPbkybJeRz5b9)
   - If so, check which LLM providers are affected (eg. Vertex / Anthropic)

3. **Check LLM provider status:**
   - [Anthropic API Status](https://status.anthropic.com/)
   - [GCP Vertex AI Status](https://status.cloud.google.com/)
   - Check if the LLM provider is experiencing issues.

3. **Check for recent changes:**
   - Review recent changes mentioned under Recent changes section.
   - If a recent change caused the issue, consider rolling back.

## Possible Resolutions

- N.A. We don't have historical data on this alert's resolutions.

## Dependencies

- [Anthropic API](https://status.anthropic.com/)
- [GCP Vertex AI](https://status.cloud.google.com/)
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
