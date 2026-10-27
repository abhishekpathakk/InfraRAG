## Chef Hybrid

In this approach the certificate is stored in a role unencrypted, where the key is stored in [chef vault](chef_vault.md).

### Replacement

Make sure you know the cert role (e.g. `ops-infra-sentry`), key data bag and item (e.g. `gitlab-sentry`, `_default`) and eventual fields (if they differ from `ssl_certificate` and `ssl_key`). Refer to the certificate table for that information.

1. Obtain the new certificate from [SSLMate](https://sslmate.com/console/orders/).
1. When replacing the key (not required when only replacing the certificate), create a local backup of the key data bag, by executing (Since the role is in git, there is no need to manually back that up)

   ```shell
   knife vault show -Fj ${data_bag} ${item} > ${data_bag}_bak.json
   ```

1. Format the new certificate (and/or key) to fit into JSOJSON properly and copy the output to the clipboard. (The following command is executed with GNU sed)

   ```shell
   sed -E ':a;N;$!ba;s/\r{0,1}\n/\\n/g' ${new_certificate}.pem
   ```

1. Update the Chef certificate role field with the newly prepared certificate `$EDITOR roles/${cert_role}.json`.

   1. Validate the JSON by running `jq . roles/${cert_role}.json`.
   1. Create an MR, have it reviewed and apply it to production.

1. When replacing the key (not required when only replacing the certificate) update the values in the data bag. Make sure to only edit the fields that were specified. Some data bags may contain multiple keys!

   ```shell
   knife vault edit ${data_bag} ${item}
   ```

   This should give you an error if the new data bag is not proper JSON. Still you should validate that by running `knife vault show -Fj ${data_bag} ${item} | jq .`. If that runs successfully, you have successfully replaced the key! Congratulations!
1. Finally trigger a chef-run on the affected node(s). This should happen automatically after a few minutes, but it is recommended to observe one chef-run manually. If that runs successfully, you have successfully replaced the certificate! Congratulations!

### Rollback of a replacement

Sometimes stuff goes wrong. Good thing we made a backup! :)

If you replaced the key:

1. Copy the contents of `${data_bag}_bak.json` into your clipboard
1. Update the values in the data bag. Clear out the whole write-buffer and paste the JSON you just copied.

   ```shell
   knife vault edit ${data_bag} ${item}
   ```

Always:

1. Find and revert the git commit in which you updated the certificate role.
1. Apply the reverted commit
1. Run chef
1. Done!
