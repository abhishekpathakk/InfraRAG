# AI Gateway rate limits

LLM providers apply limits to concurrency, requests per minute, input tokens per minute, and output tokens
per minute, which are configured in the AI Gateway (see
[the Inference limits documentation](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/docs/inference_limits.md))

If our usage is approaching or exceeding these limits, we may need to request an increase. See provider-specific
instructions below.

## Anthropic

You can see the current limits set for the
GitLab account in <https://platform.claude.com/settings/limits>.

To request a rate limit increase, contact the Anthropic team via the `#ext-anthropic` channel.

If you do not have access to the GitLab Anthropic account, please
[file an Access Request](https://gitlab.com/gitlab-com/team-member-epics/access-requests/-/issues/new).
