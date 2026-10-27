## Forum / Discourse

### Replacement

1. Obtain the new certificate from [SSLMate](https://sslmate.com/console/orders/).
1. ssh to `forum.gitlab.com`
1. Create backup of the certificate (replacing 2019 with whatever year the old certificate started in)

  ```shell
  sudo cp /var/discourse/shared/standalone/ssl/ssl.crt{,.2019}
  ```

1. Copy the new certificate to the server as `/var/discourse/shared/standalone/ssl/ssl.crt` and change the permissions to `544` and owner to `root:root`
1. `sudo restart app` to restart discourse
1. Done!

### Rollback of a replacement

Sometimes stuff goes wrong. Good thing we made a backup! :)

1. Move the new certificate in a safe place
1. Restore the old certificate by renaming or copying it back.
1. `sudo restart app`
1. Done!
