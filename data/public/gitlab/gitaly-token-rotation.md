# Gitaly token rotation

The overall process involves these steps:

1. Suppress token validation while rotating the token
1. Generate a new token
1. Rotate the token in the Gitaly VM fleet
1. Rotate the token in the GitLab application
1. Resume token validation

## Execution

To disable enforcement of Gitaly authentication:

- [ ] Disable enforcement of Gitaly authentication by setting `default_attributes['omnibus-gitlab']['gitlab_rb']['gitaly']['configuration']['auth']['transitioning'] = true` in `gprd-base-stor-gitaly` and `gprd-base-stor-gitaly-cny` Chef/Cinc roles

```json
  "default_attributes": {
    [...]
    "omnibus-gitlab": {
      "gitlab_rb": {
        [...]
        "gitaly": {
          "configuration": {
            "auth": {
              "transitioning": true
            },
          [...]
```

- [ ] If you are in a rush, you can apply the changes to the Gitaly servers by force. `knife ssh -C3 'roles:gprd-base-stor-gitaly OR roles:gprd-base-stor-gitaly-cny' 'sudo chef-client'`
- [ ] Verify by checking a Gitaly VM that the `/etc/gitlab/gitlab.rb` has the transitioning field set correctly.
- [ ] Monitor `gitaly_authentications_total` using a promql query like below. You should see that the count will drop to 0 as more are reporting enforced as false. The count should move from the number of Gitaly servers to 0 as Chef changes are converged across the fleet.

```
count(gitaly_authentications_total{env="gprd",enforced="true",status=~".*ok"}) or vector(0)
```

Generate a new token and update 1password

- [ ] Create a new random token `echo "$(pwgen 16 1)-gprdtoken"`
- [ ] Find the `gprd Gitaly Token` secret in the `Infra Vault` in 1password and update that value with the new secret.

Replace the current `auth_token` in Vault for Gitaly VMs

- [ ] Navigate to the location in Vault where the `gitlab-omnibus-secrets` are kept. Usually in the `chef` engine at this path `env/gprd/shared/gitlab-omnibus-secrets`.
- [ ] Chef/Cinc does not limit to a version, so you can make a new version of these secret and update the `gitaly_token` field in the blob.
- [ ] Verify on a Gitaly VM that the new token is being updated in the `/etc/gitlab/gitlab.rb` file.

Replace the current `auth_token` in Vault for GitLab.com application

- [ ] Navigate to the location in Vault where the `token` key is kept. Usually in the `k8s` engine at this path `env/gprd/ns/gitlab/gitaly/auth`.
- [ ] Add a new version of this secret that matches what we put in 1password.
- [ ] Follow instructions provided for our Kubernetes Infrastructure:
  <https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/README.md#secret-rotation>

Verify that the tokens are updated in all the places and ensure that authentication is working as expected.

- [ ] Once the VMs have the new secret and the GitLab.com application secret is updated, monitor this query to verify that the tokens match. The count should be the same as the number of Gitaly VMs.

```
count(gitaly_authentications_total{env="gprd",enforced="false",status=~".*ok"}) or vector(0)
```

- [ ] Finally, re-enable authentication enforcement by reverting the `['auth']['transitioning']` setting added to the roles in the first step
- [ ] If you are in a rush, you can apply the changes by force. `knife ssh -C3 'roles:gprd-base-stor-gitaly OR roles:gprd-base-stor-gitaly-cny' 'sudo chef-client'`
- [ ] Monitor that the enforced=true and status=ok is returning to the same count as the number of Gitaly VMs

```
count(gitaly_authentications_total{env="gprd",enforced="true",status="ok"}) or vector(0)
```

## Rollback

Follow the execution steps, but instead of creating a new token via `pwgen` set the old token in the vault.

## Helpful Links

- [Enable auth transitioning mode](https://docs.gitlab.com/administration/gitaly/configure_gitaly/#enable-auth-transitioning-mode)
- [Gitaly monitoring queries](https://docs.gitlab.com/administration/gitaly/monitoring/#queries)
