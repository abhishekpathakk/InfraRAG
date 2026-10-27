# Database Access via Teleport

> [!warning] Always follow the change management process
>
> To make changes in production, open a change request in
> [#production](https://gitlab.enterprise.slack.com/archives/C101F3796) using
> `/change declare`. An SRE will execute the steps on your behalf. See the
> [change management process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/)
> for details.

Use this guide to connect to a PostgreSQL database shell using Teleport's
`tsh` command-line tool. If you prefer, you can alternatively open a session directly through
the [web UI](https://production.teleport.gitlab.net/web/cluster/production.teleport.gitlab.net/resources).

## Prerequisites

- Teleport access via Okta (see [getting access](./getting_access.md)).
- `tsh` is installed (see [installation instructions](./getting_access.md#install-tsh)).
- `psql` installed. It is recommended to install it via
  [Homebrew](https://brew.sh) as the `mise` or `asdf` builds lack the OpenSSL
  support required by Teleport and will cause SSL errors.

  ```bash
  brew install postgresql@18
  ```

## Process

> [!note] Default access
> Read-only access to non-production databases is assigned by default via the
> `non-prod-database-ro` role, so skip the **Request Access** steps and go
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

1. Identify the role you need:

   For all read/write access (both prod & non-prod), review the
   [change management process](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/)
   to determine whether a change request is required. If unsure, reach out to an
   SRE for assistance. **EMs cannot typically approve read-write access.**

   | Database               | Env      | Access type | Role                                         |
   | ---------------------- | -------- | ----------- | -------------------------------------------- |
   | `main`, `ci`, or `sec` | Non-prod | Read-only   | No request needed, skip to [Log in](#log-in) |
   | `main`, `ci`, or `sec` | Non-prod | Read/write  | `non-prod-database-rw`                       |
   | `registry`             | Non-prod | Read-only   | No request needed, skip to [Log in](#log-in) |
   | `registry`             | Non-prod | Read/write  | `non-prod-database-registry-rw`              |
   | `customersdot`         | Non-prod | Read-only   | No request needed, skip to [Log in](#log-in) |
   | `customersdot`         | Non-prod | Read-write  | No request needed, skip to [Log in](#log-in) |
   | `main`, `ci`, or `sec` | Prod     | Read-only   | `prod-database-ro`                           |
   | `main`, `ci`, or `sec` | Prod     | Read/write  | `prod-database-rw`                           |
   | `registry`             | Prod     | Read-only   | `prod-database-registry-ro`                  |
   | `registry`             | Prod     | Read/write  | `prod-database-registry-rw`                  |
   | `customersdot`         | Prod     | Read-write  | `prdsub-customersdot-database-rw`            |

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

   Three items of information are needed to log into a database:

   - `db-user`: `console-ro` for read-only, or `console-rw` for read/write
   - `db-name`: Usually `gitlabhq_production`, or `gitlabhq_registry` for registry dbs
   - Teleport database name (`db`): Can be found using `tsh db ls`. Common
   database names are also listed [below](#reference-common-database-names) for
   your convenience.

   ```bash
   tsh db ls                    # all registered databases
   tsh db ls environment=gstg   # non-production
   tsh db ls environment=gprd   # production
   ```

2. Log in to retrieve database credentials

   ```bash
   tsh db login \
     --db-user=<db-user> \  # `console-ro` or `console-rw`
     --db-name=<db-name> \  # usually `gitlabhq_production`
     <db>                   # See "Gather the necessary details" above
   ```

3. Connect to the database shell:

   ```bash
   tsh db connect <Database Name>
   ```

### Admin access

> [!warning] Restricted
> Admin access is restricted to DBREs and SREs during incidents only

The `database-admin` role grants superuser access to any database.

```bash
tsh request create \
  --proxy=production.teleport.gitlab.net \
  --request-roles=database-admin \
  --request-reason="<GitLab issue URL or ZenDesk ticket URL>"

tsh login --request-id=<request-id>
```

## Next Steps

- Access requests are temporary and expire after 12 hours, but may be used
  across multiple sessions. Renew it before or after expiration using the same
  request process.
- Learn how to [connect a database GUI client](https://goteleport.com/docs/connect-your-client/third-party/gui-clients/)
  such as pgadmin in Teleport's docs

## Support

- For help with Teleport or the approval process, ask in
  [#security_help](https://gitlab.enterprise.slack.com/archives/C094L6F5D2A).
- To report a Teleport bug, [open an issue](https://gitlab.com/gitlab-com/gl-security/product-security/product-security-engagements/product-security-requests/-/issues/new?description_template=infrasec-teleport)
  with Infrastructure Security.

## Reference: Common database names

| Description           | Env      | db                            | db-name               |
| --------------------- | -------- | ----------------------------- | --------------------- |
| Main                  | Non-prod | `db-main-replica-gstg`        | `gitlabhq_production` |
| CI                    | Non-prod | `db-ci-replica-gstg`          | `gitlabhq_production` |
| Security              | Non-prod | `db-sec-replica-gprd`         | `gitlabhq_production` |
| Registry              | Non-prod | `db-registry-replica-gstg`    | `gitlabhq_registry`   |
| DR archive — main     | Non-prod | `db-main-dr-archive-gstg`     | `gitlabhq_production` |
| DR archive — CI       | Non-prod | `db-ci-dr-archive-gstg`       | `gitlabhq_production` |
| DR archive — registry | Non-prod | `db-registry-dr-archive-gstg` | `gitlabhq_registry`   |
| Main                  | Prod     | `db-main-replica-gprd`        | `gitlabhq_production` |
| CI                    | Prod     | `db-ci-replica-gprd`          | `gitlabhq_production` |
| Security              | Prod     | `db-sec-replica-gprd`         | `gitlabhq_production` |
| Registry              | Prod     | `db-registry-replica-gprd`    | `gitlabhq_registry`   |
| DR archive — main     | Prod     | `db-main-dr-archive-gprd`     | `gitlabhq_production` |
| DR archive — CI       | Prod     | `db-ci-dr-archive-gprd`       | `gitlabhq_production` |
| DR archive — registry | Prod     | `db-registry-dr-archive-gprd` | `gitlabhq_registry`   |

## Troubleshooting

### `tsh request create` timed out

`tsh request create` will wait for approval and return once the request is
approved, denied, or expires.

If it times out before a decision, check
[#teleport-requests](https://gitlab.enterprise.slack.com/archives/C06Q2JK3YPM)
slack channel or the [Teleport Web UI](https://production.teleport.gitlab.net/web/requests)
for the request ID — you don't need to re-request if it was approved.

### `psql: error: could not connect to server: Connection refused`

The local `psql` client may be overriding the user and database name. Pass them
explicitly:

```bash
tsh db connect \
  --db-user=console-ro \
  --db-name=<gitlabhq_production|gitlabhq_registry> \
  <database_name>
```

### `psql: error: SSL SYSCALL error: ... signal: segmentation fault`

This occurs when `psql` is installed via `asdf` or `mise`. Use the Homebrew
version instead:

1. Install via Homebrew if not already done:

   ```bash
   brew install postgresql@18
   ```

2. Get the full connection command from `tsh`:

   ```bash
   tsh db config --format=cmd <database_name>
   ```

3. Re-run the command, replacing the `psql` binary path with the Homebrew one:

   ```bash
   $(brew --prefix postgresql@18)/bin/psql "<connection string from step 2>"
   ```

### `psql: error: sslmode value "verify-full" invalid when SSL support is not compiled in`

Your `psql` binary was not compiled with OpenSSL support. Switch to the Homebrew
version as described above.

### `failed to add one or more keys to the agent`

See [getting_access.md — Troubleshooting](./getting_access.md#error-failed-to-add-one-or-more-keys-to-the-agent).

### Verbose output

```bash
tsh --debug db connect <database_name>
```
