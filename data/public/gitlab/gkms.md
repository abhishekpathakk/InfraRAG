## GKMS and Vault

At the time of this writing, the GKMS secrets are in the process of being
migrated into Vault under the `chef/` KV mount. Both share the same process for
certificate management.

### Automation

Renewal of SSLMate-issued certificates is automated via the
[Certificates Updater](https://gitlab.com/gitlab-com/gl-infra/certificates-updater).
This tool pulls all Chef secrets from GKMS and Vault (under the `chef/` KV
mount), checks the validity of every certificate found with a valid associated
private key, and updates them with a new certificate from
[SSLMate](https://sslmate.com/) when possible. It runs every Monday and
Thursday at 10:00 UTC in a
[scheduled CI pipeline](https://gitlab.com/gitlab-com/gl-infra/certificates-updater/-/pipeline_schedules)
on GitLab.com, renewing certificates that expire within the next 4 weeks
(`RENEW_WEEKS_IN_ADVANCE`). Certificates that SSLMate cannot issue, such as
internal CA certificates, are not renewed by this tool.

In cases where this automation fails to update a certificate (or skips it), you can follow the instructions below.

### Replacement

Make sure you know the item (e.g. `frontend-loadbalancer gprd`) and fields (if they differ from `ssl_certificate` and `ssl_key`). Refer to the certificate table for that information.

1. Obtain the new certificate from [SSLMate](https://sslmate.com/console/orders/).
1. (GKMS only) Create a local backup of the `gkms-vault`:

   ```shell
   ./bin/gkms-vault-show ${item} > ${item}_bak.json
   ```

1. (Vault only) Note the current version of the Vault secret:

   ```shell
   vault kv metadata get -mount=chef  env/${env}/${item} | grep current_version
   ```

1. Format the new certificate (and/or key) to fit into JSON properly and copy the output to the clipboard. (The following command is executed with GNU sed)

   ```shell
   sed -E ':a;N;$!ba;s/\r{0,1}\n/\\n/g' ${new_certificate}.pem
   ```

1. Update the values in the `gkms-vault`. Make sure to only edit the fields that were specified. Some data bags will contain multiple certificates!

   ```bash
   # GKMS
   ./bin/gkms-vault-edit ${item}
   # Vault
   glsh vault edit-secret chef env/${env}/${item}
   ```

   See [../vault/usage.md#interact-with-vault-secrets] for more information on how to access and edit Chef secrets in Vault.

1. (GKMS only) This should give you an error if the new `gkms-vault` is not proper JSON. Still you should validate that by running `./bin/gkms-vault-show ${item} | jq .`. If that runs successfully, you have successfully replaced the certificate! Congratulations!
1. Finally trigger a chef-run on the affected node(s). This should happen automatically after a few minutes, but it is recommended to observe one chef-run manually.

### Rollback of a replacement

Sometimes stuff goes wrong. Good thing we made a backup! :)

#### GKMS

1. Copy the contents of `${item}_bak.json` into your clipboard
1. Update the values in the `gkms-vault`. Clear out the whole write-buffer and paste the JSON you just copied.

   ```shell
   ./bin/gkms-vault-edit ${item}
   ```

1. Done!

#### Vault

1. Rollback to the previous version of the secret:

   ```shell
   vault kv rollback -mount=chef -version=${version} env/${env}/${item}
   ```

1. Done!
