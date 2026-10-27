# Pulp Runbook - Functional Operations

## Overview

GitLab uses Pulp to store and distribute RPM and DEB packages for different RHEL-based and Debian-based OS distributions. This runbook covers the functional operation perspective of Pulp and our usage patterns.

[[_TOC_]]

## Core Concepts

Pulp uses three key components for package management:

1. **Repository** - A collection of packages that maintains multiple versions based on changes made during its lifetime.

2. **Publication** - A distributable snapshot of a repository pointing to a specific repository version. All our repositories are configured to automatically create a new publication whenever a new package is uploaded.

3. **Distribution** - The endpoint through which a repository is made accessible to users. Each distribution has a base path defined relative to the Pulp instance root. Distributions can point to either:
   - A specific publication, or
   - A repository (always pointing to the publication of the latest repository version) - **this is what we use**

**Terminology note:** To avoid confusion, this document uses "Pulp repository" and "Pulp distribution" when referring to Pulp-specific concepts. "OS distribution" refers to systems like "Debian Trixie", "Ubuntu Noble", or "AlmaLinux 9".

## Repository Structure

APT and RPM repositories differ in their structure and naming pattern, as described below. Pulp distributions and their corresponding repositories have the same names, and the name is indicative of the final URL where they get served from.

### APT Repositories

**Background:** Theoretically, an APT repository can hold packages for different architectures and OS distributions, provided there are no [duplicate packages](https://wiki.debian.org/DebianRepository/Format#Duplicate_Packages).

**Our challenge:** Packages for a GitLab version created by omnibus-gitlab for different OS distributions all share the same version string but have different content (and checksums). This makes them duplicate packages that would overwrite each other in a single repository. We have 10 years of packages versioned this way that must remain accessible to customers.

**Our solution:** One Pulp repository per OS distribution for each component:

- Example repositories: `gitlab-gitlab-ee-debian-trixie`, `gitlab-gitlab-ce-ubuntu-noble`
- Each repository holds packages for different architectures (APT repositories [segregate metadata by architecture](https://wiki.debian.org/DebianRepository/Format#A.22Packages.22_Indices))

**Access pattern:**

```
https://packages.gitlab.com/<organization>/<namespace>/<os>/<distribution>
```

**Example sources.list entry:**

```
deb https://packages.gitlab.com/gitlab/gitlab-ee/debian/trixie trixie main
```

### RPM Repositories

**Structure:** Each architecture of each OS version gets its own Pulp repository. This allows serving packages for each architecture at different endpoints, saving users from downloading metadata for other architectures. This matches the standard structure used by upstream EL distributions.

**Access pattern:**

```
https://packages.gitlab.com/<organization>/<namespace>/<os>/<version>/<architecture>
```

**Example repo configuration:**

```
baseurl=https://packages.gitlab.com/gitlab/gitlab-ee/el/9/$basearch
```

## Repository Management

### Creating and Updating Repositories

Pulp repositories and distributions are [managed by code](https://gitlab.com/gitlab-org/build/pulp-repository-automation).

**To add a new OS distribution:**

1. Edit the YAML configuration file
2. Add the new OS to the relevant components

**Important:** Repository deletion must be done manually to prevent accidental data loss.

## Uploading Packages

**Prerequisites:**

- [Pulp CLI configured and authenticated](./README.md#configuration)
- Credentials for a user account with upload permissions.
- Read access to the [`gitlab-com-pkgs-builds` bucket](../gitlab-com-pkgs/overview.md), to publish a package a pipeline did not upload. Check it with `gcloud storage ls gs://gitlab-com-pkgs-builds/`.

### DEB Package Upload

```bash
pulp deb content upload \
  --file=<path_to_file> \
  --repository=<pulp-repository> \
  --distribution=<os-distribution> \
  --component=main
```

Example:

```bash
pulp deb content upload \
  --file=gitlab-ee_18.0.0-ee.0_amd64.deb \
  --repository=gitlab-gitlab-ee-debian-trixie \
  --distribution=trixie \
  --component=main
```

**Note:** The `--distribution` flag is required even though there's a Pulp repository per OS distribution. This ensures Pulp properly generates metadata files for each OS distribution.

### RPM Package Upload

```bash
pulp rpm content upload \
  --file=<path_to_file> \
  --repository=<pulp-repository>
```

Example:

```bash
pulp rpm content upload \
  --file=gitlab-ee-18.0.0-ee.0.el9.x86_64.rpm \
  --repository=gitlab-gitlab-ee-el-9-x86_64
```

**Important:** The uploaded file must match the architecture corresponding to the repository.

**Note:** RPM uploads don't require `--distribution` or `--component` flags because RPM internals create metadata
files from all packages in a repository without a concept of "distributions".

### Publishing a Package a Pipeline Did Not Upload

A build job can pass while its upload job never runs.
The package then exists only as a job artifact, and it disappears when that artifact expires.
The symptom is a `404` for one package, while others from the same build are present.

The examples below use a FIPS deb for Ubuntu Jammy.
An internal release version `<version>-internal<n>` maps to the package version `<version>+internal<n>-0`.

> [!WARNING]
> Do not rebuild. A new pipeline creates a different binary, and it re-uploads published packages, which replaces them.

1. Confirm the build job passed in [omnibus-gitlab on dev.gitlab.org](https://dev.gitlab.org/gitlab/omnibus-gitlab), for example `Ubuntu-22.04-fips-branch`.

2. Download the package and its checksum into a scratch directory with 1 GB free. FIPS builds use a `_fips` platform suffix. The job artifacts hold the same files if you have no bucket access, but branch build artifacts expire 1 day after the job.

   ```bash
   gcloud storage cp gs://gitlab-com-pkgs-builds/ubuntu-jammy_fips/gitlab-fips_<version>+internal<n>-0_amd64.deb{,.sha256} .
   ```

3. Verify the checksum. Stay in that directory and leave the `.sha256` file in it. The file names the package with a `pkg/<platform>/` prefix, and `shasum -c` resolves that path from the current directory, so only the deb moves.

   ```bash
   mkdir -p pkg/ubuntu-jammy_fips
   mv gitlab-fips_<version>+internal<n>-0_amd64.deb pkg/ubuntu-jammy_fips/
   shasum -c gitlab-fips_<version>+internal<n>-0_amd64.deb.sha256
   ```

4. Upload it. Repository names drop the `_fips` suffix, so a FIPS deb goes to the same repository as the `gitlab-ee` deb of that series. Packages are about 1 GB, so expect a few minutes.

   ```bash
   pulp deb content upload \
     --file=pkg/ubuntu-jammy_fips/gitlab-fips_<version>+internal<n>-0_amd64.deb \
     --repository=gitlab-pre-release-ubuntu-jammy \
     --distribution=jammy \
     --component=main \
     --chunk-size=10000000
   ```

5. Verify the result. An empty list means the upload did not land.

   ```bash
   pulp deb content list \
     --package=gitlab-fips \
     --version="<version>+internal<n>-0" \
     --field version \
     --field relative_path
   ```

6. Test a download of the `relative_path` it reports, as described in [Testing Package Downloadability](#testing-package-downloadability). If that download returns `404`, follow [Troubleshooting](./troubleshooting.md).

For an RPM package, the platform directory, file name, and repository all differ.
Upload it with the [RPM Package Upload](#rpm-package-upload) command, and check it with [RPM Package Validation](#rpm-package-validation).

## Downloading Packages

### Public packages

#### Using UI

Packages can be searched and downloaded via the UI at <https://packages.gitlab.com/ui/browse>. For example:

- RPM: Visit <https://packages.gitlab.com/ui/browse/gitlab/gitlab-ee/el/10/x86_64>
- DEB: Visit <https://packages.gitlab.com/ui/browse/gitlab/gitlab-ee/debian/bookworm>
- Click on any package name to download

#### Using `curl`

```bash
curl -LOJf https://packages.gitlab.com/gitlab/gitlab-ee/el/10/x86_64/Packages/g/gitlab-ee-18.10.1-ee.0.el10.x86_64.rpm
```

### Private packages

Pulp credentials can be found on the Vault item `k8s/ops-gitlab-gke/pulp/users`.

#### Using UI

> [!NOTE]
> Downloading private packages (e.g. `pre-release`) is not possible via Pulp UI. Please use
> `curl` with credentials as described below.

Because of a limitation of the UI, private repositories cannot be explored step by step like public packages. We
need a full repository path to visit directly:

- Click `SET CREDENTIALS` on the upper right corner of the UI and set a credential that has access to the private
  repository.
- Access the private repository, e.g. <https://packages.gitlab.com/ui/browse/gitlab/pre-release/el/9/x86_64>

#### Using `curl`

> [!WARNING]
> Passing credentials directly in the command exposes them in shell history and process listings.
> Use `--netrc` with a `~/.netrc` file as a safer alternative:
>
> ```
> machine packages.gitlab.com login <user> password <pass>
> ```
>
> Then run:

```bash
curl -LOJf --netrc https://packages.gitlab.com/gitlab/pre-release/el/10/x86_64/Packages/g/gitlab-ee-18.10.1-ee.0.el10.x86_64.rpm
```

Otherwise, you can also specify the username and password directly:

```bash
curl -LOJ -u "user:pass" https://packages.gitlab.com/gitlab/pre-release/el/10/x86_64/Packages/g/gitlab-ee-18.10.1-ee.0.el10.x86_64.rpm
```

## User Management

Check [user management documentation](./user-management.md) for details on creation and management of users and roles in Pulp.

## Operational Commands Reference

### List Repositories

```bash
pulp deb repository list --limit=1000
pulp rpm repository list --limit=1000
```

Note: Use `--offset` flag to implement pagination.

### List Distributions

```bash
pulp deb distribution list --limit=1000
pulp rpm distribution list --limit=1000
```

Note: Use `--offset` flag to implement pagination.

### List All Packages

```bash
pulp deb content list --limit=1000
pulp rpm content list --limit=1000
```

Note: Use `--offset` flag to implement pagination.

### List All Versions of a Specific Package

```bash
pulp deb content list --package=gitlab-ee --limit=1000
pulp rpm content list --name=gitlab-ee --limit=1000
```

**Note:** Additional filters are available - check `--help` for each command.

### Validate a Specific Package Version Exists

To verify a specific package version exists in Pulp's content store:

**Prerequisites:**

- [Pulp CLI configured and authenticated](./README.md#configuration)

#### DEB Package Validation

```bash
pulp deb content list \
  --package=<package-name> \
  --version="<exact-version>" \
  --field version \
  --field relative_path
```

**Examples:**

Validate a stable release:

```bash
pulp deb content list \
  --package=gitlab-ee \
  --version="18.10.0-ee.0" \
  --field version \
  --field relative_path
```

Validate a release candidate:

```bash
pulp deb content list \
  --package=gitlab-ee \
  --version="18.10.0-rc42.ee.0" \
  --field version \
  --field relative_path
```

Validate an internal release:

```bash
pulp deb content list \
  --package=gitlab-ee \
  --version="19.3.4+internal1-0" \
  --architecture=amd64 \
  --field version \
  --field relative_path
```

An empty output means the package does not exist. Note that an internal release version `<version>-internal<n>` maps to the package version `<version>+internal<n>-0`.

Validate a nightly build:

```bash
pulp deb content list \
  --package=gitlab-ee \
  --version="18.10+stable.2398694953.4845434f-0" \
  --field version \
  --field relative_path
```

Validate an auto-deploy package:

```bash
pulp deb content list \
  --package=gitlab-ee \
  --version="18.10.202603181806-6ee48bcc3b8.f3f3da516cc" \
  --field version \
  --field relative_path
```

#### RPM Package Validation

For RPM packages, both `--version` and `--release` fields are needed for precise matching:

```bash
pulp rpm content list \
  --name=<package-name> \
  --version="<version>" \
  --release="<release>" \
  --field version \
  --field release \
  --field location_href
```

**Examples:**

Validate a stable release:

```bash
pulp rpm content list \
  --name=gitlab-ee \
  --version="18.10.0" \
  --release="ee.0.el9" \
  --field version \
  --field release \
  --field location_href
```

#### Interpreting Results

| Output                             | Meaning                                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------------------------- |
| `[]` (empty)                       | Package not in Pulp -- never uploaded, or incorrect version string                          |
| Records present                    | Content exists in the store                                                                 |
| Content exists but 404 on download | Package not added to repository/publication -- see [Troubleshooting](./troubleshooting.md)  |

#### Version String Formats

GitLab DEB packages use these version formats:

| Release Type              | Example Version                                        |
| ------------------------- | ------------------------------------------------------ |
| Stable release            | `18.10.0-ee.0`                                         |
| Release candidate         | `18.10.0-rc42.ee.0`                                    |
| Internal release          | `18.10.0+internal0-0`                                  |
| Stable branch auto-deploy | `18.10+stable.<pipeline_id>.<commit>-0`                |
| Nightly build             | `18.10.YYYYMMDDHHMM-<gitlab_commit>.<omnibus_commit>`  |
| Release nightly           | `18.10.0+rnightly.<pipeline_id>.<commit>-0`            |

GitLab RPM packages use separate version and release fields:

| Release Type      | Version   | Release                                   |
| ----------------- | --------- | ----------------------------------------- |
| Stable release    | `18.10.0` | `ee.0.<os>` (e.g., `ee.0.el9`)            |
| Release candidate | `18.10.0` | `rc42.ee.0.<os>` (e.g., `rc42.ee.0.el9`)  |

**Note:** The `--version` flag requires an **exact match**. If unsure of the exact version string, omit the `--version` flag and use `--limit=20` to examine available versions.

#### Testing Package Downloadability

If you need to verify a package is actually downloadable (not just present in the content store):

**For DEB packages:**

```bash
# Get the relative_path from content list
pulp deb content list \
  --package=gitlab-ee \
  --version="18.10.0-ee.0" \
  --field relative_path

# Test download (replace with your distribution base URL and filename)
curl -I "https://packages.gitlab.com/gitlab/gitlab-ee/debian/pool/bookworm/main/g/gitlab-ee/<filename>.deb"
```

**For RPM packages:**

```bash
# Get the location_href from content list
pulp rpm content list \
  --name=gitlab-ee \
  --version="18.10.0" \
  --release="ee.0.el9" \
  --field location_href

# Test download (replace with your distribution base URL and filename)
curl -I "https://packages.gitlab.com/gitlab/gitlab-ee/el/9/x86_64/<filename>.rpm"
```

| HTTP Status     | Meaning                                                                   |
| --------------- | ------------------------------------------------------------------------- |
| `200 OK`        | Package is downloadable                                                   |
| `404 Not Found` | Package not in publication -- see [Troubleshooting](./troubleshooting.md) |

**Note:** All GitLab Pulp repositories have `autopublish: true` enabled. If a package exists in content but returns 404 on download, this typically indicates a publication or distribution configuration issue rather than a missing upload.

### Create a Publication Manually

If auto-publish fails, manually create a publication:

```bash
pulp deb publication create --repository=<pulp-repository-name>
pulp rpm publication create --repository=<pulp-repository-name>
```

### List Tasks by State

```bash
pulp task list --state=waiting
pulp task list --state=running
pulp task list --state=failed
```

### Check Task Status

```bash
pulp task show --href=<pulp-task-href>
```
