# Adding New Resources

## Pre-requisites

1. The resource has network access to the Teleport Cluster's proxy
   (internal.production.teleport.gitlab.net).
1. The resource has access to a
   [join method](https://goteleport.com/docs/reference/deployment/join-methods)
   (default is GCP)

## Adding virtual machines (via Chef)

1. Ensure that the [gitlab-teleport](https://gitlab.com/gitlab-cookbooks/gitlab-teleport)
   cookbook is in the runlist (see [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo)).
1. Ensure that the `environment` and `service` attributes are set.
1. Ensure that the join method is configured via the `config` attribute.

Note that the cookbook may also be used to deploy a Teleport bot service
(Machine & Workload Identity).

## Adding kubernetes resources (via Helm)

1. Add the new cluster resources to the [Teleport Agent
   chart](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/teleport-agent).
1. Ensure that the `labels.environment` and `labels.service` attributes are set.
1. Ensure that the join method is configured via the `joinParams` attribute.

## Manual approach (avoid doing this, use IaC approaches instead)

1. On your local machine, log into tsh.
1. Use `tctl tokens add --ttl=5m --type=node` to generate a new token.
1. On the resource node, stop teleport with `systemctl stop teleport`.
1. On the resource node, edit the `/etc/teleport/config.yaml` file, and add the generated token to the `token_name` field.
1. Start up the teleport service again on the resource node: `systemctl start teleport`.

## Updating Roles

Ensure that the labels applied to the resource match existing roles so that the
correct users can access it.

If you have added a new db-type (for example), you may need to add it to
existing roles defined in Terraform.
[Here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests/10978)
is an example merge request to add the new `sec` db-type to existing roles.

## Reference

[Join Services with a Secure Token](https://goteleport.com/docs/enroll-resources/agents/join-services-to-your-cluster/join-token/)
