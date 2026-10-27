# Code Suggestions

## About Code Suggestions

### Contact Information

- **Group**: Create:Code Creation
- **Handbook**: [Code Creation](https://handbook.gitlab.com/handbook/engineering/ai/ai-coding/)
- **Slack**: [#g_code_creation](https://gitlab.enterprise.slack.com/archives/C048Z2DHWGP)

### Core Functionality

GitLab Duo Code Suggestions provides two distinct AI-powered coding assistance functions:

- Code Completion:
  - Powered by Codestral 25.08 from a weighted pool: Fireworks AI (weight 75) and Vertex AI (weight 25)
  - Response time: Satisfied < 2.5s, Tolerated < 10s
  - Activated automatically while typing
- Code Generation:
  - Powered by Claude Sonnet 4.6 on Vertex AI
  - Response time: Can exceed 5 seconds for complex algorithms, satisfied < 30s
  - Triggered by natural language comments followed by Enter or empty functions
  - Supports streaming in JetBrains and Visual Studio IDEs

### IDE Integration

Available in:

- VS Code (GitLab Workflow extension v6.2.2+)
- JetBrains IDEs (GitLab extension v3.6.5+)
- Visual Studio (GitLab extension v0.51.0+)
- Neovim (GitLab plugin v1.1.0+)
- GitLab Web IDE

### Connectivity

Primary Connection Method:

- Direct to AI Gateway: Almost all users (including most GitLab Self-Managed customers) connect directly from their IDE to the AI Gateway at [cloud.gitlab.com](https://cloud.gitlab.com:443)

Alternative Connection Method:

- Through Self-Managed Instance: GitLab Self-Managed customers can optionally configure their installation to route Code Suggestions requests through their local GitLab Rails application instead of direct connections. This alternative method is configurable by the GitLab administrator but is less commonly used

Authentication Flow:

- Users authenticate using personal access tokens for secure API connections
- For Self-Managed users calling the AI Gateway directly, authentication follows the same pattern as SaaS users
- Detailed authentication and authorization flows are documented in the [AI Gateway Architecture Design](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/ai_gateway/#authentication--authorization)

Additional Resources:

- Complete connectivity diagrams and technical details: [Code Creation Engineering Overview](https://handbook.gitlab.com/handbook/engineering/ai/ai-coding/feature-stewardship/code_suggestions/engineering_overview/#code-completion)

### Requirements

- Premium or Ultimate subscription with GitLab Duo Pro or Enterprise add-on
- Assigned seat in GitLab Duo subscription
- GitLab 17.2+ for optimal experience
- Personal access token for secure API connection

### Usage Patterns

- We typically see more usage Monday to Friday and less on the weekends.
- The traffic tends to be highest during traditional working hours in the different regions.

### Documentation

- [Code Suggestions Engineering Overview](https://handbook.gitlab.com/handbook/engineering/ai/ai-coding/feature-stewardship/code_suggestions/engineering_overview/)
  - Interaction diagrams
  - Dependencies
- [Code Suggestion Documentation](https://docs.gitlab.com/user/project/repository/code_suggestions/) - GitLab Documentation

## Service Level Indicators (SLIs)

Our monitoring is built around two key SLIs that align with our core functionality:

### Code Completions SLI (`server_code_completions`)

- **Source**: `model_inferences_total` and `inference_request_duration_seconds` with `unit_primitive="complete_code"`. Counts completions on every API version, v4 and the deprecated v2.
- **Target**: Response time < 2.5 seconds
- **Tolerated**: Response time < 10 seconds. Apdex counts non-streaming requests only.
- **Failure**: The model call raised an error (`error="yes"`).
- **Excluded**: Amazon Q completions. They report `unit_primitive="amazon_q_integration"`.
- **User Impact**: When errors occur, users don't see any completions in their editor. This fails silently, no error is presented. In practice, users can retry fetching the completions by continuing to write code.
- **Models Used**: Fireworks AI (weight 75) and Vertex AI (weight 25), both Codestral 25.08. Customers can pin other models through model selection. Those models appear under their own engine.
  - `inference_other` - Tracks both Codestral providers. They run through LiteLLM and report `model_engine="litellm-completion"`. Split them by `model_name`: `codestral-2508` is Fireworks, `codestral-2` is Vertex.
  - `inference_anthropic` - Tracks pinned Claude models called through the Anthropic API (`anthropic-chat`).

### Code Generation SLI (`server_code_generations`)

- **Source**: `model_inferences_total` and `inference_request_duration_seconds` with `unit_primitive="generate_code"`. Counts generations on every API version, v4 and the deprecated v2 and v3.
- **Target**: Response time < 30 seconds
- **Apdex**: Counts non-streaming requests only.
- **Failure**: The model call raised an error (`error="yes"`).
- **User Impact**: When errors occur, users don't receive generated code from their comments. This fails silently, no error is presented. In practice, users can retry generating the code by pressing Enter again.
- **Models Used**: Claude Sonnet 4.6 on Vertex AI (default)
  - `inference_other` - Tracks the default. It runs through LiteLLM and reports `model_engine="litellm-chat"`.
  - `inference_anthropic` - Tracks pinned Claude models called through the Anthropic API (`anthropic-chat`).

*Note: The alerts and dashboards in the Initial Triage section below are organized by these SLIs*

## Initial Triage

### Alerting

Code Suggestions alerts are surfaced through AI Gateway alerts. You can find more about that in the [AI Gateway Runbook / Monitoring-Alerting Section](README.md#monitoringalerting).

The specific alerts for Code Suggestions are:

- [AiGatewayServiceServerCodeCompletions...](https://dashboards.gitlab.net/alerting/list?search=AiGatewayServiceServerCodeCompletions)
  - AiGatewayServiceServerCodeCompletionsApdexSLOViolation
  - AiGatewayServiceServerCodeCompletionsApdexSLOViolationRegional
  - AiGatewayServiceServerCodeCompletionsErrorSLOViolation
  - AiGatewayServiceServerCodeCompletionsErrorSLViloationRegional
- [AiGatewayServiceServerCodeGenerations...](https://dashboards.gitlab.net/alerting/list?search=AiGatewayServiceServerCodeGenerations)
  - AiGatewayServiceServerCodeGenerationsApdexSLOViolation
  - AiGatewayServiceServerCodeGenerationsApdexSLOViolationRegional
  - AiGatewayServiceServerCodeGenerationsErrorSLOViolation
  - AiGatewayServiceServerCodeGenerationsErrorSLViloationRegional

#### Alert: ApdexSLOViolations

This could be caused by an increase in latency or an increase in errors. The user impact will be slower response times when generating code suggestions.

Client Behavior During Slow Requests:

- Loading Indicator: Users will see a loading indicator in their IDE extension while waiting for suggestions
- If users wait without typing or navigating, slow suggestions will eventually appear in their editor once the request completes
- If users continue typing, moving the cursor, or navigating to different files while waiting, the delayed suggestion will be discarded when it finally returns (as it's no longer contextually relevant)
- User Experience Impact: During SLO violations, users may experience:
  - More frequent "loading" states in their editor
  - Reduced suggestion frequency as they continue working while requests are pending

#### Alert: ErrorSLOViolation

This is caused by an increase in 5XX errors. When this happens the user will not see code suggestions appear in their IDE.

### AI Gateway Apdex Error

**Step 1: Determine which AI Service is affected**

Go to the [AI Gateway Dashboard](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview) and identify if the issue is related to code completions, code generation, or some other service.

If this is a more general AI Gateway problem, refer to the [AI Gateway Runbook](README.md)

**Step 2: Investigate Code Completions Issues**

If the dashboard indicates a code completions problem:

1. Check SLI Apdex metrics
    - Server_code_completions SLI Apdex: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&ffrom=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-792111394)
    - Apdex attribution for server_code_completion: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-200)
2. Analyze Error Rates
    - View Server_code_completions Errors: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-193)
    - Investigate error details in [Log dashboard](https://log.gprd.gitlab.net/app/r/s/8WeMd) or [search](https://log.gprd.gitlab.net/goto/d21f8880-f0a7-11ed-a017-0d32180b1390) in Elastic (data view = pubsub-mlops-inf-gprd-*)
3. Review Latency Issues
    - Check p95 server_code_completions Latency: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-192)
    - Examine charts in Grafana ([AI Gateway Overview](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd)) for `inference_other` (both Codestral providers, split by `model_name`)
    - Consider these factors:
      - Is the issue isolated to one region or affecting all regions?
      - Is it specific to a particular model?
      - Is it related to a specific provider (vertex/other/anthropic)?
      - Has there been an increase in requests (RPS)?
    - Review the [log dashboard](https://log.gprd.gitlab.net/app/dashboards#/view/6c947f80-7c07-11ed-9f43-e3784d7fe3ca?_g=(refreshInterval:(pause:!t,value:0),time:(from:now-6h,to:now)))
      - Has there been an increase in prompt length? This (also called input tokens) can lead to slower response times

**Step 3: Investigate Code Generation Issues**

If the dashboard indicates a code generation problem:

1. Check SLI Apdex metrics
    - Server_code_generation SLI Apdex: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-886296197)
    - Apdex attribution for server_code_generation: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-220)
2. Analyze Error Rates
    - View Server_code_generation Errors: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-213)
    - Investigate error details in [Log dashboard](https://log.gprd.gitlab.net/app/r/s/8WeMd) or [search](https://log.gprd.gitlab.net/goto/d21f8880-f0a7-11ed-a017-0d32180b1390) in Elastic (data view = pubsub-mlops-inf-gprd-*)
3. Review Latency Issues
    - Check p95 server_code_generation Latency: [Grafana Link](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=from=now-3h&to=now&&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-212)
    - Examine charts in Grafana ([AI Gateway Overview](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-3h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd)) for `inference_other` (the LiteLLM-served default) or `inference_anthropic` (Anthropic API pins)
    - Consider these factors:
      - Is the issue isolated to one region or affecting all regions?
      - Is it specific to a particular model?
      - Is it specific to a provider (vertex/other/anthropic)?
      - Has there been an increase in requests (RPS)?
    - Review the [log dashboard](https://log.gprd.gitlab.net/app/dashboards#/view/6c947f80-7c07-11ed-9f43-e3784d7fe3ca?_g=(refreshInterval:(pause:!t,value:0),time:(from:now-6h,to:now)))
      - Has there been an increase in prompt length? This (also called input tokens) can lead to slower response times

## Common Resolution Steps

### High Error Rates

When experiencing high error rates, the most common cause is quota or rate limit issues with our LLM providers. Follow these steps to diagnose and resolve:

#### Step 1: Check Provider Quota Utilization

Different providers have different methods for checking quota usage:

- In the [saturation panel of the AI gateway service dashboard](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview?orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-runway&var-environment=gprd&viewPanel=panel-1217942947). This lists all quota as measured clientside.
- Anthropic: Check usage and rate limits at [platform.claude.com](https://platform.claude.com/settings/usage#rate-limits)
- Vertex AI (Google Cloud): Check quota usage at [console.cloud.google.com](https://console.cloud.google.com/iam-admin/quotas?referrer=search&project=gitlab-ai-framework-prod)
- Fireworks: we are using dedicated deployments, so no quota limitations, but a deployment could get overwhelmed by too many requests. Fireworks provides some eyes into this in their [console](https://app.fireworks.ai/account/usage?type=deployments).

#### Step 2: Correlate Quota Issues with Error Patterns

After checking quotas, correlate findings with error logs:

- Review the Log dashboard for HTTP 429 (rate limit) or 403 (quota exceeded) errors
- Look for error patterns that align with the provider experiencing quota issues
- Check if errors are concentrated during peak usage hours

#### Step 3: Escalation and Resolution

If quota/rate limit issues are confirmed:

1. **Immediate**: Document the affected provider, quota type, and current utilization percentage
2. **Contact Provider**: Reach out through the appropriate channel:
    - Google Cloud/Vertex: #ext-google-cloud slack channel
    - Anthropic: #ext-anthropic slack channel
    - Fireworks: #ext-gitlab-fireworks slack channel (internal access required)
3. **Include Details**: When contacting providers, include:
    - Current quota utilization percentage
    - Time range when issues began
    - Expected traffic patterns requiring higher limits
    - Business impact summary

#### Step 4: Monitor Resolution

- Continue monitoring the AI Gateway Dashboard error rates
- Verify quota increases take effect by re-checking provider consoles
- Confirm error rates return to normal baseline levels

### Latency Issues

1. An increase in traffic can lead to latency issues. This could be caused by saturation of the LLM which takes longer to respond.
2. If there is an increase in tokens sent, then the requests could take longer.
3. Check out the [AI Gateway Scalability Runbook](README.md#scalability)

### Provider-Specific Problems

1. If there are problems with a specific provider we will need to work directly with them to resolve the problem. Here are some ways to reach out in slack:
    - #ext-google-cloud
    - #ext-anthropic
    - #ext-gitlab-fireworks (not currently public)

### Prolonged Provider Outages - Model Failover

When a provider experiences extended outages or degraded performance that cannot be quickly resolved, Code Suggestions has a failover system to switch traffic to alternative model providers using feature flags.

When to Consider Failover:

- Provider outage expected to last more than 30 minutes
- Sustained high error rates (>10%) from a specific provider
- Severe latency issues affecting user experience across a provider
- Provider communication indicates extended maintenance windows

Failover Process:

- Failover procedures require coordination with on-call engineers and must follow established protocols
- Complete failover documentation and procedures: [Code Suggestion Failover Runbook](../duo/code_suggestion_failover.md)
- Feature flag changes require appropriate approvals and should be coordinated through incident management procedures

Important Notes:

- Failover is a significant operational change that affects all users
- Always document the business justification and expected duration before initiating failover
- Monitor closely after failover to ensure the alternative provider can handle the traffic load
- Plan for failback once the primary provider issues are resolved

## Dashboards

### Logging

Be sure the datasource (data view) is “pubsub-mlops-inf-gprd-*”

Look for the json.jsonPayload.path `/v4/code/suggestions`. Rails-proxied requests go there: generations from GitLab 19.1 and later, completions on GitLab.com, and completions from Self-Managed and Dedicated instances on GitLab 19.5 and later ([gitlab-org/gitlab!259616](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/259616)). Self-Managed and Dedicated instances on 19.4 and earlier still send completions to `/v2/code/completions`, unless an admin enabled the `code_completion_v4_endpoint` feature flag manually. Language Server direct connections send completions to `/v2/completions` until the IDE extensions bundle Language Server 9.27.0 or later ([gitlab-lsp!4169](https://gitlab.com/gitlab-org/editor-extensions/gitlab-lsp/-/merge_requests/4169)). Older GitLab versions send `/v2/code/generations`, and some clients use `/v3/code/completions`. All four legacy paths are deprecated, with removal planned for GitLab 21.0.

`json.jsonPayload.code_suggestion_type` (`code_editor_completion` or `code_editor_generation`) is only logged for v3 and v4 requests, so filter v2 traffic by `json.jsonPayload.path`.

- [mlops](https://log.gprd.gitlab.net/goto/d21f8880-f0a7-11ed-a017-0d32180b1390)
- [request rate](https://log.gprd.gitlab.net/goto/c4faac00-f612-11ed-a017-0d32180b1390)
- [request latency](https://log.gprd.gitlab.net/goto/b423c240-f612-11ed-8afc-c9851e4645c0)

[Code Suggestions Overview Dashboard](https://log.gprd.gitlab.net/app/r/s/8WeMd)

- For both code completion and code generation
- Request rates
- Error counts by error code
- User counts
- Latency
- Prompt lengths

[Code Completion Durations](https://log.gprd.gitlab.net/app/r/s/q6PL3)

- Latency for code completion (not code generation)
- Broken down by region, provider, model name

There are specific filtered versions as well:

- Fireworks: <https://log.gprd.gitlab.net/app/r/s/8igQR>
- Vertex: <https://log.gprd.gitlab.net/app/r/s/VciTn>
- Codestral: <https://log.gprd.gitlab.net/app/r/s/7MASa>
- Codestral on Fireworks: <https://log.gprd.gitlab.net/app/r/s/bi6fU>
- Codestral in europe-west-2: <https://log.gprd.gitlab.net/app/r/s/yER2Q>
- Codestral in us-east-4: <https://log.gprd.gitlab.net/app/r/s/5y4Dt>
- Qwen: <https://log.gprd.gitlab.net/app/r/s/PbBOj>

### Grafana Dashboards

[AI Gateway Overview](https://dashboards.gitlab.net/d/ai-gateway-main/ai-gateway3a-overview)

Since all the Code Suggestions traffic flows through the AI Gateway, this dashboard is the best place to look. It has information about other services too (like Duo Chat).

`SLI Details:inference *`

Details on the various model providers:

- Codestral completions on Fireworks and on Vertex both run through LiteLLM and appear in `inference_other` with `model_engine` `litellm-completion`. Split them by `model_name`: `codestral-2508` is Fireworks, `codestral-2` is Vertex.
- The code generation default, Claude Sonnet 4.6 on Vertex AI, also runs through LiteLLM and appears in `inference_other` as `litellm-chat`.
- `inference_anthropic` tracks models called through the Anthropic API (`anthropic-chat`), for example pinned Claude models. Other Duo features use it too.
- `inference_vertex` (`vertex-ai`) and `inference_fireworks` (`fireworks_ai`) track older model classes that the current Code Suggestions defaults do not use.

`SLI Details: server_code_completions` or `SLI Details: server_code_generations`

- Details on latency, requests per second (RPS), and errors
- Overall breakdown, per API endpoint, per Region

[Code Suggestions Error Budget Details](https://dashboards.gitlab.net/d/stage-groups-detail-code_creation/c704560) or [Code Suggestions Group Dashboard](https://dashboards.gitlab.net/d/stage-groups-code_creation/stage-groups3a-code-creation3a-group-dashboard)

These have much less valuable information than the AI Gateway Overview dashboard

### Tableau

This is a good source of information for historic data, but is not updated in real time. Most of these charts can be filtered by model, provider, deployment type (SaaS, SM, etc), and more.

- [Overview](https://10az.online.tableau.com/#/site/gitlab/views/PDCodeSuggestions/README)
- [Latency](https://10az.online.tableau.com/#/site/gitlab/redirect_to_view/10829850)
- [Quality / Acceptance Rate](https://10az.online.tableau.com/#/site/gitlab/redirect_to_view/10829848)
- [Number of Requests](https://10az.online.tableau.com/#/site/gitlab/redirect_to_view/10829846)

### Sentry

Limited alerting data can be found in [Sentry](https://new-sentry.gitlab.net/organizations/gitlab/issues/?query=is%3Aunresolved+code+suggestions&referrer=issue-list&statsPeriod=7d)
