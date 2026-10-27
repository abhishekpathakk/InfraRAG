# dev.gitlab.org host

`dev.gitlab.org` does not have a bastion host. SREs with access can SSH directly to the `all-in-one`
VM using the configuration in this document.

In order to gain access, a user's SSH key must be in the appropriate [data bag in `chef-repo`], and
the user's groups must include one of the groups mentioned in the [`dev-gitlab-org` role].

## How to configure ssh login

SSH config is managed via [`glsh ssh-config`](ssh-config.md).

Once your config is in place, test it by connecting via SSH to the bastion host:

```bash
ssh dev.gitlab.org
```

[`dev-gitlab-org` role]: https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/9b87a93f0d726b8e85fd8d13a75dc40824ded094/roles/dev-gitlab-org.json#L22-27
[data bag in `chef-repo`]: https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/data_bags/users
