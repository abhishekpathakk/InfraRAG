# Pulp Runbook - Deleting a Package

## Overview

Deleting a package from Pulp is a multi-step process. Pulp tracks content by
an internal `pulp_href` identifier, and package removal requires explicitly
modifying repository content rather than deleting the package directly.

This runbook covers how to remove a package from a Pulp RPM or Debian/APT
repository. The repository type is auto-detected; no separate script or flag
is needed. The package content artifact is not deleted from Pulp storage - it
is only removed from the target repository version going forward. Existing
repository versions that included the package remain unchanged (Pulp
repository versions are immutable).

## Prerequisites

- [Pulp CLI configured and authenticated](./README.md#configuration)

## Usage

Run [scripts/pulp/delete-package.sh](../../scripts/pulp/delete-package.sh) with exact package name and version, and a partial repository name. An optional `--profile` flag selects a Pulp CLI profile. Use `--dry-run` to verify the search resolves to the correct package and repository before making any changes:

```bash
scripts/pulp/delete-package.sh --name <name> --version <version> --repository <search> [--profile <profile>] [--dry-run]
```

Examples:

```bash
scripts/pulp/delete-package.sh --name gitlab-ee --version 18.9.1 --repository sles-12.5-x86_64
scripts/pulp/delete-package.sh --name gitlab-ee --version 18.9.1 --repository sles-12.5-x86_64 --profile ops
scripts/pulp/delete-package.sh --name gitlab-ee --version 18.9.1 --repository sles-12.5-x86_64 --dry-run
```

> [!NOTE]
> If the search terms match more than one package or repository, the script will print the matches and exit with an error asking you to be more specific.
> This is intentional to make sure that there is only one package deleted at one time, since this action is destructive.

> [!NOTE]
> `--name` matches the package name field for both ecosystems. The underlying
> Pulp CLI filter differs (`--name` for RPM, `--package` for Debian/APT), but
> the script handles this automatically based on the auto-detected repository type.
>
> For Debian/APT repositories, `--version` must include the release suffix,
> e.g. `18.0.5-ee.0` rather than `18.0.5`. To find the exact version string:
>
> ```bash
> pulp [--profile <profile>] deb content list \
>   --repository-version $(pulp [--profile <profile>] deb repository show --name <repo> | jq -r '.latest_version_href') \
>   --package <name> \
>   --field version
> ```

The script will:

1. Look up the package href by filename
2. Remove the package from the repository
3. Verify the package is absent from the latest repository version
4. Clean up the orphaned content artifact from storage using `orphan cleanup --content-hrefs`

**Warning:** Avoid running `pulp orphan cleanup` without `--content-hrefs` as
it will delete all unreferenced content across all repositories.

If you do not know the exact repository name, search by partial name first:

```bash
pulp repository list --name-contains '<partial-name>'
```

## Notes

- **Repository version history is immutable**: Previous repository versions
  that included the package are not affected. Only the new version onward will
  reflect the removal.
- **Auto-publish**: Our repositories are configured to auto-publish on content
  change. A new publication pointing to the new repository version will be
  created automatically after the content modify operation completes.
