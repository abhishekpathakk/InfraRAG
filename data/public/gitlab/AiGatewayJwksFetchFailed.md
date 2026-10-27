# AI Gateway JWKS fetch failed (Slack notification)

**Table of Contents**

[TOC]

## Ownership

This alert is owned by the [Authentication Group](https://handbook.gitlab.com/handbook/engineering/development/sec/software-supply-chain-security/authentication/).

## Overview

As explained in the Cloud Connector Auth [overview](./../README.md#authentication), we need to fetch public keys from gitlab.com and CustomersDot to perform Token-based Authentication.

There may be situations when we are not able to obtain the keys - for example, when gitlab.com or CustomersDot are unavailable, if there is a network or other problems.

We cache the keyset for performance reasons, but inability to refresh/receive keys for a prolonged period of time will lead to AI Gateway degradation. We will not be able to start new pods (`readiness` probe will fail) or verify requests.

To react to this situation in a timely manner, we configured Elastic Watch that will [notify](#alert-behavior) the team in Slack.

## Metrics

The alert fires when we log one of these errors to `cloud_connector` logger in AI Gateway:

- `"Old JWKS re-cached: some key providers failed"`
- `"Incomplete JWKS cached: some key providers failed, no old cache to fall back to"`

Note: we aim to improve error logging (in particular: cleaner messages/labels) under [this issue](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/issues/92).

Elastic Watch is configured in [elastic-cloud](https://gitlab.com/gitlab-com/gl-infra/observability/elastic-cloud/-/blob/main/environments/gitlab-logs-prod/watchers/cloud_connector_ai_gw_oidc_fetch_failures.json).

## Alert Behavior

The alert does not invoke pagers but is posted to the [#g_scss_authentication_alerts](https://gitlab.enterprise.slack.com/archives/C07EQ7F6P0D) Slack channel.

## Troubleshooting sequence

1. Act on the alert. React with `:eyes:` (eyes emoji) if you are investigating for transparency and visibility.
2. Understand who is affected. Depending on which key provider(s) is/are failing, different audiences are impacted. Every related log record labelled with `oidc_provider` string. You can see errors with `oidc_provider` equal to:
   - `Gitlab`: users from gitlab.com are impacted: pod(s) that report JWKS fetch problems can't authenticate requests to AI Gateway coming from there.
   - `CustomersDot`: self-managed customers. Note that similar to the `gitlab.com`, only AI Gateway pods that reported the problem can't authenticate the request. That means that some (or most - if, for example, only a single pod is faulty) requests will come through. That would still result in disruptions for the customer's workflow (e.g., sometimes Duo Chat will post an error instead of response or not every code completion will not be served).
3. Understand the urgency.
   - If you only see `"Old JWKS re-cached: some key providers failed"`:
     - Estimate the volume of errors. You can group by pods:
       - If we see a huge spike of these events, check [the next section](#possible-resolutions) to dig deeper.
       - A relatively small and sparse amount of these should not result in service degradation. It's still worth following up with troubleshooting (but with less urgency than in other scenarios). Please open a follow-up issue.
     - Avoid stating Cloud Connector key rotation. If there is a Cloud Connector key rotation in progress, notify rotation DRIs in the rotation issue.
   - If you also see `"Incomplete JWKS cached: some key providers failed, no old cache to fall back to"`:
     - In general, this should only happen in the `readiness`, so there should be a related `json.jsonPayload.cloud_connector_ready : false` record. [Elastic query for AI GW](https://log.gprd.gitlab.net/app/r/s/eQS2H).  We fail to start up the new pod. It will retry again in a while.
     - Action: Monitor for the error volume and check the relevant provider's keys endpoint availability. A large amount of failed `readiness` probes means we can't rotate AI Gateway pods. The incident should be declared.
4. Conclude the investigation. When the investigation is complete, indicate it with `:white_check_mark:` (green square with white checkmark emoji) for transparency.

## Possible resolutions

- If either [gitlab.com](https://gitlab.com/.well-known/openid-configuration) or [CustomersDot](https://customers.gitlab.com/.well-known/openid-configuration) keys endpoints are unavailable:
  - [Authentication Group](https://handbook.gitlab.com/handbook/engineering/development/sec/software-supply-chain-security/authentication/) own the endpoint so ask them to help with troubleshooting.
  - Check if there were some changes made around the endpoint (e.g. in controller that serves it or routing). Raise an issue if you find a potential root cause. Note that the keys endpoint implementations in gitlab.com and CustomersDot are separate and not (yet) unified.
  - If there is a wider service outage (so it's not only keys endpoints): raise the incident, tag service owners to troubleshoot and help with the resolution.
- If keys endpoints are available on both providers, but we keep receiving the alerts:
  - Proceed with investigating relevant errors within `cloud_connector` logger in AI Gateway:
    - Check if there is a correlation with a certain provider or not. If a certain provider fetches are failing, that may mean:
      - Transient error on the provider side - refer to the dedicated availability/health dashboards and proceed from there.
      - There may be some configuration issue in AI Gateway. You can check with AI Gateway experts.
    - If both providers fail uniformly:
      - Check if `gitlab-cloud-connector` Python package was updated recently:
        - Check the package version that [AI Gateway uses](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/blob/main/pyproject.toml#L53) and when it was last updated.
        - If there was a recent update, refer to the Python part of the `gitlab-cloud-connector` [library](https://gitlab.com/gitlab-org/cloud-connector/gitlab-cloud-connector/-/tree/main/src/python).
        - In the library, refer to the relevant changes to investigate and find the authors.
      - Check for general AI Gateway availability and health during the alert window. Ask AI Gateway team.
  - Re-check that the Elastic Watch conditions are correct (in case there is a problem with the rule itself or it was updated).
