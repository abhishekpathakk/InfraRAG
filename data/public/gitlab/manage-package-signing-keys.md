# GPG Keys for Package Signing

We support two different types of GPG signatures: **packages** and **repository metadata**.

This document is concerned with the signing of **packages**, which is done on package build pipelines. For
repository metadata signing, which is done on the package management system, see [manage repository metadata signing
keys](../pulp/manage-repository-metadata-signing-keys.md).

As described in the [omnibus project for GitLab](https://gitlab.com/gitlab-org/omnibus-gitlab/-/blob/master/doc/package-information/signed_packages.md),
GitLab, Inc. provides signed packages starting with the release of `9.5`, and
all packages on stable trees from that point forward as well (e.g. `9.3.x` as
of August 22, 2017). The package signing keys are managed by the
[Build Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/gitlab-delivery/build/),
with the [Security Team](https://handbook.gitlab.com/handbook/security/)
over seeing and verifying that the best practices are followed.

The notes contained here are intended to provide documentation on how keys are generated, maintained, revoked, and used in combination with the Omnibus GitLab CI & GitLab's Package Hosting System.

## Implementation workflow

For a complete implementation, the following will be done:

* [Generate and securely store the private keys](./generate-gpg-key-pair.md)
* Package signing in CI on all supported stable branches.
* Documentation for activation and verification.
* Publish the public keys
  * To a public PGP key server, such as `pgp.mit.edu`
  * **GitLab's Package Hosting System**: All associated repositories on `packages.gitlab.com`
    (`https://packages.gitlab.com/app/<user>/<repo>/gpg#gpg-packagekeys`)
  * **Pulp**: Upload the public key to the
    [`pulp-resources-automation`](https://gitlab.com/gitlab-com/gl-infra/pulp-resources-automation) repository:
    * Go to `files/<env>/gpgkey/<product>`:
      * There are two products: `gitlab` and `runner`
      * Production environment: `environments/ops/gpgkey`
      * Test environment: `environments/pre/gpgkey`
    * Upload the public key with the file name `<key-id>.pub.gpg`
      * Do *not* confuse and overwrite the `gpg.key` file, which is the repository metadata signing key
    * These files will be uploaded and served by Pulp.
* Publicly post about addition of the signing, and how to activate on existing installations. Provide links to the documentation on activation and verification.

## Key storage location

The location of the Omnibus package signing key can be found by searching for
a secure note in the Build vault in 1Password.

## Securing Keys

Managing private keys follows the best practice of Least Privileged Access, and
access to the storage location and passphrase itself is highly restricted. These
two items *should never* be stored together.

* There is a private, highly restricted location for the key itself to be stored.
* There is a private, highly restricted vault for the key's passphrase to be stored.
* **Security** team does the actual maintenance tasks related to the key(s) to ensure separation of concerns and LPA.
* The related variables in the `dev.gitlab.com` CI jobs should be marked as private, protected, and **never** be replicated.
