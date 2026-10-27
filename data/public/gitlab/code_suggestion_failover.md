<!-- Permit linking to GitLab docs and issues -->
<!-- markdownlint-disable MD034 -->
# GitLab Code Suggestion Failover Solution

This page provides instructions for switching the LLM provider in case of an outage with the primary provider. It is intended for product and support engineers troubleshooting LLM provider outages affecting **gitlab.com** users.

---

---

## How to switch to backup for code generation

We use a [feature flag to switch which model and model provider](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/code_suggestions/prompts/code_generation/ai_gateway_messages.rb#L37) are active for code generation.

If the primary model provider experiences an outage, enable the feature flag by running the following command in the `#production` Slack channel:

```
/chatops gitlab run feature set incident_fail_over_generation_provider true
```

After the primary LLM provider is back online, we can change back to the primary model by running this command in the `#production` Slack channel to disable the feature flag:

```
/chatops gitlab run feature set incident_fail_over_generation_provider false
```

## How to switch to backup for code completion

On GitLab.com, the AI Gateway picks the code completion model from a weighted pool. This applies to `POST /v4/code/suggestions` and to the deprecated v2 endpoints that older language servers still call. The Rails feature flag `incident_fail_over_completion_provider` does not change the model. It only forces indirect access, so all Code Suggestions requests go through Rails. For more details about direct vs indirect access, see [the documentation](https://docs.gitlab.com/user/project/repository/code_suggestions/#direct-and-indirect-connections).

To move completion traffic between providers, change the weights in the AI Gateway:

1. In the AI Gateway project, open [`ai_gateway/model_selection/unit_primitives.yml`](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/ai_gateway/model_selection/unit_primitives.yml).
1. Find the `code_completions` entry and its `default_models` list. The default is `codestral_2508_fireworks` with weight 75 and `codestral_2508_vertex` with weight 25.
1. Change the weights:
   * To leave Fireworks, set Fireworks to 0 and Vertex to 100.
   * For an outage of both Fireworks and Vertex, add `claude_sonnet_4_5_20250929` as an entry with a weight. Quality and latency differ from Codestral.
1. Merge the change and deploy the AI Gateway with the expedited process. See [Expedited AI Gateway Deployments](../ai-gateway/README.md#expedited-ai-gateway-deployments).

To fail back, restore the original weights and deploy again.

Vertex quota caveat: the Vertex Codestral quota is hard-capped at 2.2M input tokens per minute per region. EU peak demand is about 5.4M. Vertex can carry about 40% of peak completions at most. Setting Vertex to 100 at peak causes quota errors.

## How to verify

* Go to [Kibana](https://log.gprd.gitlab.net/app/home#/) Analytics -> Discover
* Select `pubsub-mlops-inf-gprd-*` as Data views from the top left
* For code generation, search for `json.jsonPayload.message: "Returning prompt from the registry"`:
  * You should see `json.jsonPayload.prompt_id: code_suggestions/generations/base` and `json.jsonPayload.prompt_version <version>`
    * You can also find the template file in [this folder](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/tree/main/ai_gateway/prompts/definitions/code_suggestions/generations/base)
    * For example, if the version is 2.0.1, then the template file is `ai-assist/ai_gateway/prompts/definitions/code_suggestions/generations/base/2.0.1.yml`
    * In this file we can find the current model and model provider, for example, here we are using `claude-3-5-sonnet@20241022` provided by `vertex_ai`:

      ```
      model:
        name: claude-3-5-sonnet@20241022
        params:
         model_class_provider: litellm
         custom_llm_provider: vertex_ai
         temperature: 0.0
         max_tokens: 2_048
         max_retries: 1
      ```

* For code completion, check which model serves the traffic:
  * In Grafana (Mimir - Runway), run `sum by (model_engine, model_name) (rate(model_inferences_total{type="ai-gateway", env="gprd", unit_primitive="complete_code"}[5m]))`
  * Or in Kibana, search for `json.jsonPayload.code_suggestion_type: code_editor_completion`
  * Both providers report `model_engine="litellm-completion"`. Split them by `model_name`: `codestral-2508` is Fireworks, `codestral-2` is Vertex.
