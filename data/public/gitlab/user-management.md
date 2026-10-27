# Pulp User Management

## Overview

This runbook covers user management procedures for the Pulp service, including creating users, managing permissions, and configuring access to private repositories. Proper user management is essential for:

- Secure package upload operations
- Authenticating clients for private repository downloads
- Administrative tasks with proper audit trails
- Adherence to security best practices

## Important Notes

- Pulp does not have a "private mode" for repositories. Instead, it uses the concept of [`content_guard`](https://pulpproject.org/pulpcore/docs/user/guides/protect-content/) to protect content.
- Role assignments are critical for upload permissions. Users need both repository-specific roles and global upload roles to successfully upload packages.
  - For repository or distribution-specific roles, they need to be assigned individually to each repository/distribution respectively. There's no "regex assignment" for assigning roles to objects.
- Assign roles to groups, and assign users to groups. Avoid assigning non-global roles to users.

## Prerequisites

- [Pulp CLI configured and authenticated](./README.md#configuration)
- Admin credentials for the Pulp instance
- Understanding of the repository structure and distribution types (deb, rpm, etc.)

## User RBAC management

### Creating User

Create a new user with a secure password:

```bash
export PULP_PASSWORD=$(openssl rand -base64 32)
export PULP_USER="<pulp user>"
pulp user create --username "$PULP_USER" --password "$PULP_PASSWORD"
```

**Note**: Store the `PULP_PASSWORD` securely (e.g., in Vault) as it will be needed for authentication.

### Adding User to Group

Add the user to the group. If the group does not exist, follow the instructions [below](#creating-group) to create it.

```bash
export PULP_GROUP="<group-name>"
pulp group user add --group "$PULP_GROUP" --username "$PULP_USER"
```

## Group RBAC management

### Creating Group

We create groups, so that we can assign roles and content guards to the groups rather than individual users, making role management easier and more scalable.

```bash
PULP_GROUP="<group-name>"
pulp group create --name "$PULP_GROUP"
```

### Creating and assigning RBAC Content Guard

Content guards allow restricting access to certain resources, and they should be created and assigned to groups.

```bash
pulp content-guard rbac create --name "$PULP_GROUP"-content-guard
pulp content-guard rbac assign --name "$PULP_GROUP"-content-guard --group "$PULP_GROUP"
```

### Associating Content Guards with Distributions

We associate content guards with the distributions to protect the content (make them private).

First, retrieve the necessary `pulp_href` values:

- **Distributions**: Access the API endpoint for your distribution type:
  - (Log in using admin credentials)
  - Deb: `https://${PULP_DOMAIN}/pulp/api/v3/distributions/deb/apt`
  - RPM: `https://${PULP_DOMAIN}/pulp/api/v3/distributions/rpm/rpm`
- **Content Guard**: `https://${PULP_DOMAIN}/pulp/api/v3/contentguards/core/rbac/`

Alternatively we can use the `pulp` CLI to narrow down searches for specific path names. For example, to find distributions with paths containing "pre-release" in their base paths, we'd run:

```
pulp deb distribution list --limit 10000000 | jq -r '.[] | select(.base_path | contains("pre-release")) | .pulp_href'
```

Then, update the distribution with the content guard:

```bash
curl -u admin:$PULP_ADMIN_PASSWORD -X PATCH \
  https://${PULP_DOMAIN}/pulp/api/v3/distributions/deb/apt/<replace with distribution href>/ \
  -H "Content-Type: application/json" \
  -d '{
    "content_guard": "/pulp/api/v3/contentguards/core/rbac/<replace with content guard href>/"
  }'
```

**Note**: Adjust the distribution type (deb/rpm) based on your package type. This step uses `curl` instead of the `pulp` CLI because `pulp deb distribution update` does not support the `--content-guard` flag currently.

### Testing User Access to Content Guard

We can verify that the user can access the protected content, by running a `curl` command for the protected distribution URL, like so:

```bash
curl -u $PULP_USER:"$PULP_PASSWORD" https://${PULP_DOMAIN}/gitlab/pre-release/ubuntu/focal/
```

The user should be able to access the repository content. When `-u $PULP_USER:"$PULP_PASSWORD"` is omitted, access should be denied.

### Granting roles to groups

Although the group may have been associated with a content guard, they still require roles to view, download, and upload content.

#### Listing Available Roles

We can retrieve the list of roles for your distribution type using the `pulp` CLI, for example:

```bash
# For Deb packages
pulp role list --limit 1000 | jq '.[] | select(.name | startswith("deb."))'

# For RPM packages
pulp role list --limit 1000 | jq '.[] | select(.name | startswith("rpm."))'
```

**Note**: Even when a group is given an `owner` role, such as `deb.aptrepository_owner`, they still need `deb.aptdistribution_viewer` role to view and download the package, and `core.upload_creator` to upload content.

#### Getting object hrefs

Before assigning roles, we need to get the `pulp_href` values of the objects we want to grant roles to. You can get these values via the `pulp` CLI, for example:

```
pulp deb repository list --limit 10000000 | jq -r '.[] | select(.name | contains("pre-release")) | .pulp_href'
pulp deb distribution list --limit 10000000 | jq -r '.[] | select(.base_path | contains("pre-release")) | .pulp_href'
```

#### Assigning Roles

Roles can be assigned to a group for a specific repository or distribution's `pulp_href`. The `--object` flag does not support a regex. `--object=""` means global assign.

To upload packages, `core.upload_creator` role is required:

```bash
pulp group role-assignment add --group "$PULP_GROUP" --role core.upload_creator --object ""
```

For `apt` repositories, `deb.aptrepository_owner` role is required to associate the uploaded package to the repository:

```bash
pulp group role-assignment add --group "$PULP_GROUP" --role deb.aptrepository_owner --object "<repository pulp_href>"
```

For RPM repositories, the `rpm.rpmrepository_owner` role is required to associate the uploaded package to the repository:

```bash
pulp group role-assignment add --group "$PULP_GROUP" --role rpm.rpmrepository_owner --object "<repository pulp_href>"
```

Note: Because of an [upstream bug in the CLI](https://github.com/pulp/pulp-cli/issues/1284), the user will also need `rpm.rpmpublication_creator` role, globally

```bash
pulp group role-assignment add --group "$PULP_GROUP" --role rpm.rpmpublication_creator --object ""
```

## Common User Management Tasks

### Listing Users

```bash
pulp user list
```

### Viewing User Details

```bash
pulp user show --username "$PULP_USER"
```

### Listing Group Role Assignments

```bash
pulp group role-assignment list --group "$PULP_GROUP"
```

### Removing User from Group

```bash
pulp group user remove --group "$PULP_GROUP" --username "$PULP_USER"
```

## References

- [Pulp Content Guard Documentation](https://pulpproject.org/pulpcore/docs/user/guides/protect-content/#rbac-content-guard)
- [Pulp File RBAC Guide](https://pulpproject.org/pulp_file/docs/admin/guides/rbac/)
- [Pulp RPM-specific RBAC Guide](https://pulpproject.org/pulp_rpm/docs/admin/guides/rbac/)

## Related Issues

- [Pulp - User/Private Repo management](https://gitlab.com/gitlab-org/build/team-tasks/-/issues/92)
