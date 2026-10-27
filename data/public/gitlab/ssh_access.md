# SSH Access to a Host via Teleport

> [!warning] Always follow the change management process
>
> To make changes in production, open a change request in
> [#production](https://gitlab.enterprise.slack.com/archives/C101F3796) using
> `/change declare`. An SRE will execute the steps on your behalf. See the
> [change management process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/)
> for details.

Use this guide to initiate an SSH session using Teleport's `tsh` command-line
tool. If you prefer, you can alternatively open a session directly through the
[web UI](https://production.teleport.gitlab.net/web/cluster/production.teleport.gitlab.net/resources).

## Prerequisites

- Teleport access via Okta (see [getting access](./getting_access.md)).
- `tsh` is installed (see [installation instructions](./getting_access.md#install-tsh)).
- A user account present on the remote host that corresponds to the local part
  of your gitlab email address (e.g. `bob` if `bob@gitlab.com`).
  User accounts are typically managed by the SRE team via [Chef data bags](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/data_bags/README.md). For assistance, ask
  [#g_fleet_management](https://gitlab.enterprise.slack.com/archives/C0ACE4T2R6W).

## Process

### Request access

> [!important]
>
> When requesting access, the **Reason** field must contain a permanent link to
> a GitLab issue (or similar) outlining **what** access you require and **why**
> you need it.
>
> Otherwise your request will be rejected
> (see [Teleport Approver Workflow](./teleport_approval_workflow.md)).

> [!tip] Request access via the web interface
>
> This runbook uses the Teleport CLI, however it may sometimes be convenient to
> instead use Teleport's web interface to make an access request.
>
> Navigate to <https://production.teleport.gitlab.net/web/requests> and click
> **New Access Request**.

1. Log in to Teleport:

   ```bash
   tsh login --proxy=production.teleport.gitlab.net
   ```

2. Identify the name of the node:

   The name of the Teleport node must be provided in order to log in. This is
   usually equal to the hostname, but in some cases it may be the fully-qualified
   domain name.

   ```bash
   tsh ls --search redis   # search by node name
   tsh ls                  # all hosts
   tsh ls env=gstg         # filter by environment
   tsh ls env=gprd
   ```

3. Request access to the resource:

   ```bash
   tsh request create \
     --resource=<node name> \
     --reason="<GitLab issue URL / ZenDesk ticket URL>"
   ```

4. An automated message will appear in the
   [#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM)
   Slack channel. If you're a member of Engineering or Security, tag your direct
   manager to review the request. Otherwise, ask in the
   [#eng-managers](https://gitlab.enterprise.slack.com/archives/CU4RJDQTY)
   channel for review by any available engineering manager.

   For more information, refer to the
   [Teleport Approver Workflow](./teleport_approval_workflow.md).

5. Once approved, the Slack bot will notify you in [#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM).

6. Log in to `tsh` again, providing the ID of your approved access request

   ```bash
   tsh login --request-id=<request-id>
   ```

### Log in

1. Connect to the host:

   ```bash
   tsh ssh <username>@<hostname>
   ```

## Next Steps

- Access expires after 12 hours. Renew it before or after expiration using the
  same request process.
- [Learn about tsh's features](https://goteleport.com/docs/connect-your-client/teleport-clients/tsh)
  in Teleport's docs.

## Support

- For help with Teleport or the approval process, ask in
  [#security_help](https://gitlab.enterprise.slack.com/archives/C094L6F5D2A).
- To report a Teleport bug, [open an issue](https://gitlab.com/gitlab-com/gl-security/product-security/product-security-engagements/product-security-requests/-/issues/new?description_template=infrasec-teleport)
  with Infrastructure Security.

## Troubleshooting

### `tsh request create` timed out

`tsh request create` will wait for approval and return once the request is
approved, denied, or expires.

If it times out before a decision, check
[#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM)
slack channel or the [Teleport Web UI](https://production.teleport.gitlab.net/web/requests)
for the request ID — you don't need to re-request if it was approved.

### `failed to add one or more keys to the agent`

See [getting_access.md — Troubleshooting](./getting_access.md#error-failed-to-add-one-or-more-keys-to-the-agent).

### `Failed to launch: user: unknown user`

The user account you're trying to access does not exist on the remote host.

Either try accessing a different user account, or provision an account using
Chef (see [data bags](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/data_bags/README.md)).
When provisioning a user account via a Chef data bag, do not specify an SSH
key unless you also require direct SSH access (i.e. not via Teleport).

### Verbose output

```bash
tsh --debug ssh <user>@<hostname>
```
