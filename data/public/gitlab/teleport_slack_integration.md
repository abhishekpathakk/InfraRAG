# Teleport Slack Integration

The `teleport-plugin-slack` is used for communicating with [Slack](https://slack.com).
See this [guide](https://goteleport.com/docs/admin-guides/access-controls/access-request-plugins/ssh-approval-slack/) for running this plugin.

## Details

- This plugin is installed and configured using the
  [teleport-plugin-slack](https://goteleport.com/docs/reference/helm-reference/teleport-plugin-slack/) Helm chart
  (see [here](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/service.yaml)).
- The following roles and user are created via the
  [teleport-cluster](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/charts/teleport-cluster-config/templates/slack.yaml) chart.
  - Role `slack-access-requests-viewer`
  - Role `slack-access-requests-manager`
  - Role `bot-slack-bot`
  - Bot `slack-bot`
  - Join Token `slack-bot-token`
