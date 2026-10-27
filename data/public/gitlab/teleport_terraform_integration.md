## Teleport Terraform Integration

[Terraform](https://www.terraform.io) needs a user with required permissions to manage the Teleport cluster.
See this [guide](https://goteleport.com/docs/admin-guides/infrastructure-as-code/terraform-provider/) for more information.

- The following roles and user are created via the
  [teleport-bootstrap](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/charts/teleport-cluster-config/templates/terraform.yaml) chart.
  - Role `terraform-cluster-manager`
  - Role `bot-terraform-gcp-bot`
  - Role `bot-terraform-gitlab-bot`
  - Bot `terraform-gcp-bot`
  - Bot `terraform-gitlab-bot`
  - Join token `terraform-gcp-bot-token`
  - Join token `terraform-gitlab-bot-token`
