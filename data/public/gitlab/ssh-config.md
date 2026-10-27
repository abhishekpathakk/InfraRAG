# SSH client config (`glsh ssh-config`)

`glsh ssh-config` sets up your SSH client so that `ssh <hostname>` works for any
VM managed by Chef, proxying through the right bastion for its environment. It
writes `~/.ssh/config.d/glsh` and includes it from `~/.ssh/config`.

The config is generated from this repo so that fixes reach everyone. Don't edit
the generated file by hand, it is overwritten on the next run. Background in
[production-engineering#26738](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26738).

## Setup

Install `glsh` if you haven't yet (see the
[runbooks README](https://gitlab.com/gitlab-com/runbooks#running-helper-scripts-from-runbook)),
then:

```bash
glsh ssh-config --user YOUR_SSH_USER
```

`YOUR_SSH_USER` is your username from the
[chef-repo user data bags](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/doc/user-administration.md).
It is saved to `~/.ssh/glsh_user_name`. Later runs only need
`glsh ssh-config`.

Test it:

```bash
ssh console-01-sv-gprd.c.gitlab-production.internal hostname
```

If you still have the bastion snippet from the old onboarding docs in
`~/.ssh/config`, remove it first. It comes before the generated config and ssh
uses the first matching value for each option.

## Updating

```bash
glsh update
glsh ssh-config
```

Run this when a new environment or GCP project is added, or when the config in
this repo changes. Existing multiplexed connections keep the old settings until
they are closed:

```bash
ssh -O stop <hostname>
```

## What you get

- `ssh <hostname>` works for every VM in every Chef environment using its
  internal GCP hostname, for example
  `ssh deploy-01-sv-gstg.c.gitlab-staging-1.internal`.
- Shortcuts for the Rails consoles: `ssh gprd-console`, `ssh gstg-console`,
  `ssh dev-console`.
- Connections through the same bastion are multiplexed. Tools such as
  `knife ssh` reuse one bastion session instead of opening one per host.
- haproxy hosts connect on port 2222 without you having to specify it.
- CustomersDot hosts (`stgsub`, `prdsub`) have no bastion. Trying to ssh to one
  prints the `tsh ssh` command to use instead. See
  [CustomersDot SSH access](../customersdot/overview.md#ssh).

## Options

```text
glsh ssh-config [--dry-run] [--user USER]
```

- `--dry-run` prints the config without writing anything.
- `--user USER` sets the SSH username and remembers it for later runs.

## Troubleshooting

`Could not resolve hostname lb-bastion.<env>.gitlab.com`: the environment is in
the mapping but has no bastion. Check the environment's runbook in this
directory for how to connect.

`Permission denied (publickey)`: your key isn't on the host yet. Chef
distributes keys from the user data bags, allow up to 40 minutes after your
chef-repo MR is merged. Check that `ssh-add -L` lists the key from your data
bag.

A new GCP project isn't covered: the environment to project mapping is in
`.glsh_ssh_config.mappings.json` in this repo. Open an MR adding it.
