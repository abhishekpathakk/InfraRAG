## Chef Vault

### Replacement

Make sure you know the data bag (e.g. `about-gitlab-com`) item (e.g. `_default`) and eventual fields (if they differ from `ssl_certificate` and `ssl_key`). Refer to the certificate table for that information.

1. Obtain the new certificate from [SSLMate](https://sslmate.com/console/orders/).
1. Create a local backup of the databag, by executing

   ```shell
   knife vault show -Fj ${data_bag} ${item} > ${data_bag}_bak.json
   ```

1. Format the new certificate (and/or key) to fit into JSON properly and copy the output to the clipboard. (The following command is executed with GNU sed)

   ```shell
   sed -E ':a;N;$!ba;s/\r{0,1}\n/\\n/g' ${new_certificate}.pem
   ```

1. **Always make sure to take the chained certificate - else you will see cert verify issues later!**
1. Update the values in the data bag. Make sure to only edit the fields that were specified. Some data bags will contain multiple certificates!

   ```shell
   knife vault edit ${data_bag} ${item}
   ```

1. This should give you an error if the new data bag is not proper JSON. Still you should validate that by running `knife vault show -Fj ${data_bag} ${item} | jq .`. If that runs successfully, you have successfully replaced the certificate! Congratulations!
1. Finally trigger a chef-run on the affected node(s). This should happen automatically after a few minutes, but it is recommended to observe one chef-run manually.

### Rollback of a replacement

Sometimes stuff goes wrong. Good thing we made a backup! :)

1. Copy the contents of `${data_bag}_bak.json` into your clipboard
1. Update the values in the data bag. Clear out the whole write-buffer and paste the JSON you just copied.

   ```shell
   knife vault edit ${data_bag} ${item}
   ```

1. Done!
