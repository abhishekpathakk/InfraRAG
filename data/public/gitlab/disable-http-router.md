# Disabling routing requests through `http-router`

Whilst we're passing through the majority of the traffic to our existing gitlab.com infrastructure we have the ability to disable routing requests through to the `http-router`.
If we're seeing issues at the `http-router` layer we can disable the routing through this layer temporarily.

Steps:

1. Remove the CloudFlare Worker routes (one of the below options)
   1. Remove the the [`cloudflare-workers.tf` file](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/cloudflare-workers.tf) for the affected environment
   2. Set the `count` for the Terraform resources for affected routes to `0`
2. Create an MR and get approval
3. Apply with `atlantis apply`
