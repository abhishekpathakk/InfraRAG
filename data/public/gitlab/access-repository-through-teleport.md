# Access Git repository through Teleport

## Prerequisites

You need to have access to the Gitaly nodes on Teleport. Follow the
[steps](../teleport/Connect_to_Rails_Console_via_Teleport.md) to gain access.

Test your access by running the command:

```sh
tsh ls
```

This might open a browser window to log in, and afterward it should print dozens
of nodes you can connect to. It should includes lines like:

```text
...
gitaly-01-stor-gprd                            ⟵ Tunnel   arch=x86_64,environment=gprd,fqdn=gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-93cb.internal,hostname=gitaly-01-stor-gprd,ke...
gitaly-01-stor-gprd                            ⟵ Tunnel   arch=x86_64,environment=gprd,fqdn=gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-ccb0.internal,hostname=gitaly-01-stor-gprd,ke...
gitaly-01-stor-gprd                            ⟵ Tunnel   arch=x86_64,environment=gprd,fqdn=gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-6688.internal,hostname=gitaly-01-stor-gprd,ke...
gitaly-01-stor-gprd                            ⟵ Tunnel   arch=x86_64,environment=gprd,fqdn=gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-f33d.internal,hostname=gitaly-01-stor-gprd,ke...
...
```

## Locate the Gitaly node and repository path

When you are investigating traffic on a certain repository, you might already
have found it in Kibana. If you have the logging for an RPC hitting that
repository, you can use the fields `json.fqdn` and `json.grpc.request.repoPath`
to locate the repository in the following steps.

If you're not looking in Kibana already, check [Find a project from its hashed
storage path](find-project-from-hashed-storage.md).

## Connect to the Gitaly node

If you have the `json.fqdn`, find the unique node ID to connect with the command:

```sh
tsh ls -v | grep <fdqn>
```

For example:

```sh
$ tsh ls -v | grep gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-6688.internal
gitaly-01-stor-gprd 0c99402b-45ee-415b-bac9-b5f8e5d811d7 ⟵ Tunnel arch=x86_64,environment=gprd,fqdn=gitaly-01-stor-gprd.c.gitlab-gitaly-gprd-6688.internal,hostname=gitaly-01-stor-gprd,kernel=6.8.0-1036-gcp,service=gitaly,type=server
```

Here the node ID is `0c99402b-45ee-415b-bac9-b5f8e5d811d7`.

You can use this to ssh into that node:

```sh
tsh ssh <username>@0c99402b-45ee-415b-bac9-b5f8e5d811d7
```

Here is `<username>` whatever your `<username>@gitlab.com` email address is.

## Elevate your user

Once you're logged in, you're logged in under your own user account. But you
won't be able to access the repository. Because all repositories are owned by
the `git` user, it's the easiest to elevate yourself to the `git` user:

```sh
sudo -u git -s bash
```

We pass `-s bash` because the default shell is `/bin/sh` and `/bin/bash` is a
bit more feature-rich.

## Locate the repository

All repositories are stored at `/var/opt/gitlab/git-data/repositories`. If you
have the `repoPath` from one of the previous steps, you can `cd` into it. For
example:

```sh
cd /var/opt/gitlab/git-data/repositories/@hashed/2d/21/2d21013342cdec9c0ce1b6e4431f88800a17e4b86ba7ea288de7559ece831d60.git
```

Now you're in the Git repository and you can run `git` commands:

```sh
$ git rev-parse HEAD
e9f03dea26fd1250f6a0599b5bccda4d6b2fa2c4
```

## Use Gitaly's git

There is Git installed on the system, but usually it's pretty old. For example
if you want to run the recently added `git repo structure` command, you'll need
the Git version that comes with Gitaly.

Gitaly has a subcommand to run the Git version that ships with Gitaly:

```sh
/opt/gitlab/embedded/bin/gitaly git -c /var/opt/gitlab/gitaly/config.toml -- <git-arguments...>
```
