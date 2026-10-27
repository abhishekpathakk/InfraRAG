# Prometheus Dead Man's Snitch

## Symptoms

Prometheus SnitchHeartBeat is an always-firing alert. It's used as an end-to-end test of Prometheus through the Alertmanager.

## Possible checks

* Make sure the `SnitchHeartBeat` alert is [firing](https://alerts.gitlab.net/#/alerts?silenced=false&inhibited=false&active=true&filter=%7Balertname%3D%22SnitchHeartBeat%22%7D)
* Make sure the SnitchHeartBeat alert is not [silenced](https://alerts.gitlab.net/#/silences).
* Check [Alertmanager config](https://alerts.gitlab.net/#/status) to see if routes are pointing to correct snitch by searching for `dead_mans_snitch_`
* Check the Prometheus and Alertmanager logs to make sure they are communicating properly with <https://deadmanssnitch.com/>.

## Setting up a snitch

1. Create a new snitch in the config-mgmt repo <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/dmsnitch/main.tf>
1. Update the json array `snitchChannels` in the [`alertmanager` Vault secret](https://vault.gitlab.net/ui/vault/secrets/ci/show/ops-gitlab-net/gitlab-com/runbooks/ops/alertmanager), which [alertmanager.jsonnet](../../alertmanager/alertmanager.jsonnet) uses.
