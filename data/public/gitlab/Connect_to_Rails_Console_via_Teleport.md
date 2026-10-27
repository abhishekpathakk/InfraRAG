# Rails Console Access via Teleport

> [!warning] Always follow the change management process
>
> To make changes in production, open a change request in
> [#production](https://gitlab.enterprise.slack.com/archives/C101F3796) using
> `/change declare`. An SRE will execute the steps on your behalf. See the
> [change management process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/)
> for details.

Use this guide to open a Rails console session using Teleport's `tsh`
command-line tool. If you prefer, you can alternatively open a session directly
through the
[web UI](https://production.teleport.gitlab.net/web/cluster/production.teleport.gitlab.net/resources).

## Prerequisites

- Teleport access via Okta (see [getting access](./getting_access.md)).
- `tsh` is installed (see [installation instructions](./getting_access.md#install-tsh)).

## Process

> [!note] Default access
> Read-only access to non-prod rails consoles is assigned by default via the
> `non-prod-rails-console-ro` role, so skip the **Request Access** steps and go
> straight to [Log in](#log-in).

### Request access

> [!important]
>
> When requesting access, the **Reason** field must contain a permanent link to
> a GitLab issue (or similar) outlining **what** access you require and **why**
> you need it.
>
> Otherwise your request will be rejected
> (see [Teleport Approver Workflow](./teleport_approval_workflow.md)).

1. Identify the role you need. The following table lists some common roles for your convenience:

   For all read/write access (both prod & non-prod), review the
   [change management process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/)
   to determine whether a change request is required. If unsure, reach out to an
   SRE for assistance. **EMs cannot typically approve read-write access.**

   | Env                     | Access type | Role                                         |
   | ----------------------- | ----------- | -------------------------------------------- |
   | Non-prod                | Read-only   | No request needed, skip to [Log in](#log-in) |
   | Non-prod                | Read-write  | `non-prod-rails-console-rw`                  |
   | Non-prod (customersdot) | Read-only   | No request needed, skip to [Log in](#log-in) |
   | Non-prod (customersdot) | Rake        | No request needed, skip to [Log in](#log-in) |
   | Non-prod (customersdot) | Read-write  | No request needed, skip to [Log in](#log-in) |
   | Prod                    | Read-only   | `prod-rails-console-ro`                      |
   | Prod                    | Read-write  | `prod-rails-console-rw`                      |
   | Prod (customersdot)     | Read-only   | `prdsub-customersdot-rails-console-ro`       |
   | Prod (customersdot)     | Rake        | `prdsub-customersdot-rake`                   |
   | Prod (customersdot)     | Read-write  | `prdsub-customersdot-rails-console-rw`       |

   **customersdot** access is limited to engineers in the Monetization group (Fulfilment & Growth). For more information, refer to the
   [customers-gitlab-com repository](https://gitlab.com/gitlab-org/customers-gitlab-com/-/blob/main/doc/setup/teleport.md)

2. Log in to Teleport:

   ```bash
   tsh login --proxy=production.teleport.gitlab.net
   ```

3. Request the role:

   ```bash
   tsh request create \
     --roles=<Role> \
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

5. Once approved, the Slack bot will notify you in
   [#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM).

6. Log in to `tsh` again, providing the ID of your approved access request

   ```bash
   tsh login --request-id=<request-id>
   ```

### Log in

1. Gather the necessary details

   | Env      | Access type | **username** | **hostname**          |
   | -------- | ----------- | ------------ | --------------------- |
   | Non-prod | Read-only   | rails-ro     | console-ro-01-sv-gstg |
   | Non-prod | Read-write  | rails        | console-01-sv-gstg    |
   | Prod     | Read-only   | rails-ro     | console-ro-01-sv-gprd |

2. Open an SSH session to the target rails host

   ```bash
   tsh ssh <username>@<hostname>
   ```

3. For read-write access, once SSHed in, open the Rails console:

   ```bash
   sudo gitlab-rails console
   ```

## Next Steps

- Access requests are temporary and expire after 12 hours, but may be used
  across multiple sessions. Renew it before or after expiration using the same
  request process.
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

### Terminal type error

**Symptom:**

```
[WARNING] Could not load command "rails/commands/console/console_command". Error: The terminal
could not be found, or that it is a generic type, having too little information for curses
applications to run.
```

**Fix:** Set `TERM` to `xterm-256color`:

```bash
TERM=xterm-256color tsh ssh rails-ro@console-ro-01-sv-gprd
```

### Error: `failed to add one or more keys to the agent`

See [getting_access.md — Troubleshooting](./getting_access.md#error-failed-to-add-one-or-more-keys-to-the-agent).

### Verbose output

```bash
tsh --debug ssh rails-ro@console-ro-01-sv-gprd
```
