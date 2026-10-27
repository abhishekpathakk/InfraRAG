# Getting Access to Teleport

[Teleport](https://goteleport.com/docs/) is the *Unified Access Plane* used at
GitLab for audited, on-demand access to infrastructure resources including
servers, databases, and Rails consoles.

## Prerequisites

### Okta access

Before you can use Teleport, you must be assigned the **Teleport app** in Okta.
This is typically part of your role's baseline group assignment during
onboarding.

If your onboarding is complete and you still do not see the Teleport app listed
in Okta, open an [access request](https://handbook.gitlab.com/handbook/security/corporate/end-user-services/access-requests/)
and follow the appropriate approval process.

> [!note] Okta login unsuccessful
> Attempting to log in to Teleport directly from the Okta
> dashboard may fail with a **"Login Unsuccessful"** message. This is expected
> and does not necessarily mean you need to open an access request.
>
> Click "Please attempt to log in again", then click "Okta" under "Sign in to Teleport".

### Install tsh

The Teleport CLI client [`tsh`](https://goteleport.com/docs/reference/cli/tsh/)
must be installed on your local machine. Official packages for macOS and Linux
are available on
[Teleport's website](https://goteleport.com/download/client-tools)
(select **CLI Client Tools** from the drop down menu).

On macOS Teleport may also be installed via Homebrew:

```bash
brew install teleport
```

> [!tip]
> The syntax and options for `tsh ssh` are very similar to the standard
> `ssh` command. See [this guide](https://goteleport.com/docs/connect-your-client/tsh/)
> for more information.

## Logging In

> [!note]
>
> `production.teleport.gitlab.net` provides access to all GitLab environments,
> including production, staging, preprod and more.

### Command line interface (`tsh`)

Once you have the Teleport app assigned in Okta, log in with `tsh`:

```bash
tsh login --proxy=production.teleport.gitlab.net
```

This opens Okta in a browser window for authentication. After authenticating,
your local `tsh` session is valid and you can connect to resources.

> [!tip]
> The `--proxy=production.teleport.gitlab.net` flag must be provided the
> first time you use `tsh`, after which it will be remembered and it does not
> need to be provided again.

### Web UI

Teleport has a web interface which you can access at
<https://production.teleport.gitlab.net>. The web interface may be used as an
alternative to the CLI for most tasks, including SSH access, database console
access, making access requests, approving access requests and more.

### Teleport Connect (optional alternative to `tsh`)

Teleport Connect is a native app that provides the same access as `tsh` in a
graphical interface. Official packages for macOS and Linux
are available on
[Teleport's website](https://goteleport.com/download/client-tools)
(select **Desktop App: Teleport Connect** from the drop down menu).

On macOS Teleport Connect may also be installed via Homebrew:

```bash
brew install teleport-connect
```

## Role-based access

Teleport uses Role-Based Access Control (RBAC). Your Okta group membership
determines which Teleport roles you are assigned. Some roles are granted by
default (such as read-only non-prod access); others (such as production access)
require an explicit access request.

Access granted via a request is temporary (12 hours). It may be renewed before
or after expiration by following the same process.

Refer to the guides in [Next steps](#next-steps) for details on how to make an
access request.

## Next steps

You can use Teleport to:

* [Access the Rails console](./Connect_to_Rails_Console_via_Teleport.md)
* [Access a database](./Connect_to_Database_Console_via_Teleport.md)
* [Access a host via SSH](./ssh_access.md)
* [Approve an access request](./teleport_approval_workflow.md) (if you've been
  granted an approver role)

## Support

If you have any issues using Teleport or the approval process, ask the
Infrastructure Security team in the
[#security_help](https://gitlab.enterprise.slack.com/archives/C094L6F5D2A) Slack
channel.

To report a bug or problem with Teleport, [open an issue](https://gitlab.com/gitlab-com/gl-security/product-security/product-security-engagements/product-security-requests/-/issues/new?description_template=infrasec-teleport)
with Infrastructure Security.

## Troubleshooting

### Error: `failed to add one or more keys to the agent`

If you see:

```
ERROR: failed to add one or more keys to the agent.
agent: failure, agent: failure
```

This is caused by your `ssh-agent` configuration. Set
`TELEPORT_ADD_KEYS_TO_AGENT=no` in your environment to work around it. You can
persist this in your `~/.bashrc` or `~/.zshrc`, or prefix individual commands:

```bash
TELEPORT_ADD_KEYS_TO_AGENT=no tsh login
```

There is an open upstream
[issue](https://github.com/gravitational/teleport/issues/22326) tracking this.

### Debug

If you have issues connecting, use the `--debug` flag for verbose output:

```bash
tsh --debug login --proxy=production.teleport.gitlab.net
```
