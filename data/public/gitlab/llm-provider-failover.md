# AI Gateway: LLM Provider Failover Procedure

This runbook describes how to quickly failover from one LLM provider to another in response
to an incident (e.g. an outage or severe degradation of a specific LLM provider).

## Overview

The AI Gateway selects which model to use for each feature based on the `default_models`
configuration in
[`unit_primitives.yml`](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/ai_gateway/model_selection/unit_primitives.yml).
This configuration is baked into the deployed image, so changing it normally requires a new
MR and a full deployment cycle (~30–60 minutes).

However, the `AIGW_MODEL_SELECTION__DEFAULT_MODELS` environment variable (introduced in
[ai-assist!5498](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/merge_requests/5498))
allows overriding the default models at runtime via Vault, without a code change. Combined
with the ability to trigger a fast redeployment by retrying a deploy job, this enables a
failover in approximately **2–5 minutes**.

## Prerequisites

- Access to Vault to update the `AIGW_MODEL_SELECTION__DEFAULT_MODELS` secret. See
  [Rotating LLM Secret](README.md#rotating-llm-secret) for Vault access instructions.
- Access to the [AI Gateway security mirror environments page](https://gitlab.com/gitlab-org/security/modelops/applied-ml/code-suggestions/ai-assist/-/environments)
  to trigger a redeployment.

## Failover procedure

### Step 1: Update the Vault secret

Follow the [Runway secrets management documentation](https://docs.runway.gitlab.com/runtimes/cloud-run/secrets-management/#rotating-a-secret)
to log into Vault and update the `AIGW_MODEL_SELECTION__DEFAULT_MODELS` secret.

> **Note:** Vault access is provisioned through Okta via an IT access request if you do not already have it.

Use the links below to navigate directly to the relevant Vault secret store for each service and environment:

| Service | Staging | Production |
| ------- | ------- | ---------- |
| AIGW | [Staging](https://vault.gitlab.net/ui/vault/secrets-engines/runway/kv/list/env/staging/service/ai-gateway/) | [Production](https://vault.gitlab.net/ui/vault/secrets-engines/runway/kv/list/env/production/service/ai-gateway/) |
| DWS | [Staging](https://vault.gitlab.net/ui/vault/secrets-engines/runway/kv/list/env/staging/service/duo-workflow-svc/) | [Production](https://vault.gitlab.net/ui/vault/secrets-engines/runway/kv/list/env/production/service/duo-workflow-svc/) |

The value must be a JSON object mapping `feature_setting` names to a list of model
identifiers.

**Format:**

```
AIGW_MODEL_SELECTION__DEFAULT_MODELS='{"<feature_setting>": ["<model_identifier>", ...], ...}'
```

**Example** — failing over `duo_chat` and `code_generations` from Vertex AI to AWS Bedrock:

```
AIGW_MODEL_SELECTION__DEFAULT_MODELS='{"duo_chat": ["claude_sonnet_4_6_bedrock"], "code_generations": ["claude_sonnet_4_6_bedrock"]}'
```

**Note**: Some `feature_setting` entries may have multiple `default_models`. In that case you can set the override to
contain all those models _except_ the one whose provider is experiencing an incident. For example, if the configuration
in `unit_primitives.yml` is

```yaml
  # ...
  - feature_setting: "duo_chat"
    default_models:
      - "claude_sonnet_4_6_vertex"
      - "claude_sonnet_4_6_bedrock"
      - "claude_sonnet_4_6"
  # ...
```

... and Bedrock is having an incident, you can set the override to

```
AIGW_MODEL_SELECTION__DEFAULT_MODELS='{"duo_chat": ["claude_sonnet_4_6_vertex", "claude_sonnet_4_6"]}'
```

> **Important:** Only include the feature settings you want to override. Omitting a feature
> setting means it continues to use the default from `unit_primitives.yml`.

Track the Vault change via a [production change request](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/new)
for traceability.

### Step 2: Trigger a fast redeployment

1. [Enable expedited runway deployments](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/b33c8a11b8a0caf2e80c8a6a4637426e511098b3/docs/delivery/emergency_deployment.md?plain=0#procedure).
1. Go to the [AI Gateway security mirror environments page](https://gitlab.com/gitlab-org/security/modelops/applied-ml/code-suggestions/ai-assist/-/environments).
1. Find the **latest** deployment pipeline (the one currently serving production).
   - **Critical:** You must use the latest pipeline. Retrying an older pipeline will deploy
     an older image, which could revert previously deployed features or security fixes.
   - Verify this is the latest by checking the commit SHA against the
     [commits page](https://gitlab.com/gitlab-org/security/modelops/applied-ml/code-suggestions/ai-assist/-/commits/main).
1. Click on the pipeline link to open it.
1. Find the `Deploy [production]` job (or the relevant environment's deploy job) and click
   **Retry**.
1. The redeployment will pick up the updated Vault secret and apply the new model selection
   configuration.

### Step 3: Restore the original configuration

Once the provider incident is resolved:

1. [Disable expedited deployments](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/b33c8a11b8a0caf2e80c8a6a4637426e511098b3/docs/delivery/emergency_deployment.md?plain=0#3-disable-required-cleanup)
1. Remove the keys added in the previous steps to `AIGW_MODEL_SELECTION__DEFAULT_MODELS` (there might be preexisting
overrides you should keep).

A fast redeployment is usually not needed at this stage, and you can just wait for the next deployment pipeline for the
changes to go into effect.
