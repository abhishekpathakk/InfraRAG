# Pre-launch model releases

Some models are given to us before the provider announces them publicly.
We are expected to support these models on the day they launch.
Adding a model through `models.yml` requires a merge request, a CI pipeline, and a production deploy.
That path is too slow to hit a launch-day deadline reliably.

Pre-launch model releases let you add a model through an environment variable instead.
The model stays invisible until a feature flag is enabled.
Launch day becomes a flag flip rather than a deploy.

For how model selection works in general, see [Model selection](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/docs/model_selection.md).

## How it works

The AI Gateway reads model definitions from two places.
The first is `ai_gateway/model_selection/models.yml`, which is the normal path.
The second is the `AIGW_MODEL_SELECTION__MODEL_RELEASES` environment variable, which is backed by a Vault secret.

Models defined in the environment variable are hidden by default.
They become resolvable only when the `ai_model_release` feature flag is enabled for the requesting user.
The gateway checks this flag on every request, using the `x-gitlab-enabled-feature-flags` header.
Disabling the flag hides the models again without a restart.

The flag is for GitLab.com only. The production gateway strips it from self-managed requests through `AIGW_FEATURE_FLAGS__DISALLOWED_FLAGS`, so a self-managed admin enabling it locally has no effect.

If a model has the same `gitlab_identifier` in both places, the environment definition wins.
This lets a model exist in both during the window after launch, while the merge request that moves it into `models.yml` is still in review.

## The environment variable

`AIGW_MODEL_SELECTION__MODEL_RELEASES` holds a single JSON object on one line.
The object has two keys:

* `models`: a list of model definitions. Each entry uses the same fields as an entry in `models.yml`.
* `feature_attachments`: a map of `feature_setting` names to the lists the model should be added to.

Each entry in `feature_attachments` can set `selectable_models`, `beta_models`, and `default_models`.
The gateway appends your `selectable_models` and `beta_models` identifiers to the existing lists for that feature, but `default_models` fully replaces the existing default for that feature setting.

Example:

```json
{
  "models": [
    {
      "name": "Example Model",
      "provider": "Anthropic",
      "gitlab_identifier": "example_model",
      "description": "Example model for illustration.",
      "cost_indicator": "$$",
      "max_context_tokens": 200000,
      "model_class_provider": "anthropic",
      "family": ["claude"],
      "params": {
        "model": "example-model-1",
        "max_tokens": 8192
      }
    }
  ],
  "feature_attachments": {
    "duo_chat": {
      "selectable_models": ["example_model"],
      "beta_models": [],
      "default_models": []
    }
  }
}
```

## Rules to follow

Attach the model to the exact `feature_setting` you want it to appear in.
The keys in `feature_attachments` are matched literally against the `feature_setting` values in `unit_primitives.yml`.
An unknown key is skipped without an error, so a typo produces no warning and no model.

Classic Duo Chat and Duo Agentic Chat are different feature settings.
Use `duo_chat` for classic Duo Chat.
Use `duo_agent_platform_agentic_chat` for Duo Agentic Chat.
Attach the model to both if you want it in both.

Do not put credentials in the model parameters.
That object is validated against a strict schema, and any unrecognized field is rejected. Some parameter classes declare a recognized credential field (for example `ChatAnthropicParams.api_key`) that would pass validation, so this is a convention rather than a guarantee enforced by the schema.
Provider credentials are configured separately, through the gateway's own settings.

Keep the `gitlab_identifier` generic while a model is under embargo.
The identifier appears in API responses and in logs.
Only the `model` parameter carries the provider's model name. The API never returns that value, but internal logs and Prometheus metrics do include it.

Only one model should be under embargo at a time.
There is a single `ai_model_release` flag, and enabling it exposes every model in the environment variable at once.

## What happens when the payload is wrong

A malformed payload never stops the gateway from starting.
The gateway logs an error, discards the models from the environment variable, and continues to serve the models from `models.yml`.
This applies to invalid JSON, a wrong top-level shape, and a model definition that fails validation.

Error logs name the field that failed and the reason.
They leave out the value of that field as a precaution.

If one model in the list fails validation, the gateway skips that model and loads the rest.
The gateway also drops any feature attachment that points at a model which failed to load, and logs a warning.

## Releasing a model

The gateway reads the environment variable once, when the process starts.
Injecting a model therefore requires a new Cloud Run revision.
Do this before launch day, because it cannot be done instantly.

### Before launch

1. Confirm `ai_model_release` is disabled on GitLab.com. Treat an enabled flag as a signal to stop and investigate.
1. Confirm `ai_model_release` is still listed under `self-managed` in `AIGW_FEATURE_FLAGS__DISALLOWED_FLAGS` in the production Runway config.
1. Write the model definition and test it locally as a `models.yml` change.
1. Add the definition to the Vault secret that backs `AIGW_MODEL_SELECTION__MODEL_RELEASES`.
1. Redeploy a previous Cloud Run revision so every instance picks up the new Vault secret value. Go to the [ai-gateway deployments](https://gitlab.com/gitlab-com/gl-infra/platform/runway/deployments/ai-gateway) and re-run the last successful deployment to pick up the Vault secrets.

### On launch day

1. Enable `ai_model_release` for a few named GitLab users with `/chatops run feature set --user=<username> ai_model_release true`, and confirm the model works in production.
1. Enable the flag for everyone.
1. If a problem appears, disable the flag. The model disappears immediately, and no deploy is needed.

### After launch

1. Open a merge request that adds the model to `models.yml` and `unit_primitives.yml`. The model keeps working through the environment variable while this merge request is in review.
1. Remove the definition from the Vault secret only after that merge request is merged and deployed. Removing it earlier makes the model disappear from production.
1. Disable `ai_model_release` for everyone. The model stays available, because it now lives in `models.yml`.

Do not select an env-released model in any model selection setting, instance or group, until the flag is enabled for everyone.

## The feature flag

`ai_model_release` is an `ops` feature flag, defined in the GitLab monolith.
It is reused for every model release, so you do not need a new flag for each launch.
Do not delete the flag after a release. Disable it instead.

GitLab sends the flag to the AI Gateway from four request paths.
These are Duo Chat, Code Suggestions, Duo Agent Platform, and the model definitions fetch that fills the model picker.

The monolith caches the model definitions response.
The cache key includes the names of the enabled flags, so flipping the flag moves users to a different cache entry rather than clearing the old one. Entries live for 30 minutes, so the model picker can lag a flag change by up to that long.

## Testing locally

Set the variable in your local environment, then restart the AI Gateway.

Request the model list twice and compare the results.
Send the first request without the flag header.
Send the second request with `x-gitlab-enabled-feature-flags: ai_model_release`.

```shell
curl -s "http://localhost:5052/v1/models/definitions" \
  -H 'x-gitlab-realm: saas' \
  -H 'x-gitlab-instance-id: test' \
  -H 'x-gitlab-global-user-id: test'

curl -s "http://localhost:5052/v1/models/definitions" \
  -H 'x-gitlab-realm: saas' \
  -H 'x-gitlab-instance-id: test' \
  -H 'x-gitlab-global-user-id: test' \
  -H 'x-gitlab-enabled-feature-flags: ai_model_release'
```

Then send a chat request that names the env-released identifier in `model_metadata` with the flag off. It falls back to the default model, because every resolver goes through the gated `get_model`.

The model appears only in the second response.
Both requests reach the same process, so you should not need a restart between them.
If you do need a restart to see the difference, the flag check has moved to load time, and that is a bug.

To test through the GitLab UI, enable the flag for your user in the Rails console:

```ruby
Feature.enable(:ai_model_release, User.find_by_username('root'))
```
