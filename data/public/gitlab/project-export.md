# Project exports

We sometimes need to manually export a project. This mostly is necessary when
exporting via UI fails for some reason. Are you looking for [Exporting a Gitaly Repository](../gitaly/gitaly-repositry-export.md) instead?

## From where to run the export

Manual project exports should work from the console node. The root disk space
was increased to 200GB recently, leaving more than 150GB free space for project
exports. Typically, a project export needs twice it's size on disk space - for
extracting all files and then writing out the tar.gz archive.

**Warning:** You can't judge the size of a project export by the size shown in
the admin UI! It doesn't account for uploads. We have cases, where small
projects have more than 30GB of uploads (release files or attachments...) which
are using external object storage and need to be downloaded from there when
creating the export.

Also, the gitlab-ee version on the console might be outdated, which can lead to
compatibility problems with importing exports or other errors.

If you encounter this or really run out of disk space, run the export from the
file-node on which the repository is located. You can find that by looking up
the Gitaly storage name and relative path of the project in the Admin UI or via
rails console:

```ruby
ssh $USER-rails@console-01-sv-gprd.c.gitlab-production.internal
[ gprd ] production> p = Project.find_by_full_path('some/project')
[ gprd ] production> p.repository.storage
=> "nfs-file-cny01"
[ gprd ] production> p.repository.disk_path
=> "@hashed/a6/80/a68072e80f075e89bc74a300101a9e71e8363bdb542182580162553462480a52"
[ gprd ] production> p.pool_repository.disk_path # When a project gets forked, a pool repository is created we need to export it as well
=> "@pools/b4/3e/b43ef5538f2e6167fdc8852badbe497b50d4cfd4ed7e1b033068f1a296ee57d2"
```

## Export a project via rails-console

- ssh to the console node (or the file-node found above, if console doesn't work).
- sudo gitlab-rails console

```ruby
u = User.find_by_any_email('<your_login>+admin@gitlab.com')
p = Project.find_by_full_path('some/project')
e = Projects::ImportExport::ExportService.new(p,u)

e.execute
```

If everything works, that will create an archive, upload it to GCS, send out an
email and a cleanup job will remove locally created files later.

But there are high chances, that things fail. If you get a failure with a sentry
event id, you should look that up by going to
`https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=<long-sentry-id-number>`

### No download link and no download email

It seems that, when manually exporting, the archive file get's uploaded to GCS,
but we do not show a download link in the Web UI (under Settings -> Advanced -
Project export) and do not send out an email with the download link.

**Solution:** In the output of `p.execute` you should see the upload location,
something like
`gitlab-gprd-uploads/import_export_upload/export_file/<some-number>/<some-archive>.tar.gz`

Copy this over to the `gitlab-gprd-tmp` bucket (it has a retention policy
deleting files after 2 days and is not publicly browsable), adding a random
string to the filename, to make it secure and make the file public to share it
(secretely) with the customer:

```
# take the archive name from above
filename=<some-archive>.tar.gz
random_prefix=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c20)
gsutil cp gs://gitlab-gprd-uploads/import_export_upload/export_file/<some-number>/$filename gs://gitlab-gprd-tmp/${random_prefix}-${filename}
gsutil acl ch -u AllUsers:R gs://gitlab-gprd-tmp/${random_prefix}-${filename}
```

Now you can share the link with the customer (careful - anyone with the link can
access the file!):
`https://storage.googleapis.com/gitlab-gprd-tmp/${random_prefix}-${filename}`

### GCE credentials missing

If you get an error with `/etc/gitlab/gcs-creds.json` missing (very likely) that
means that the repository has external object storage items (e.g. Merge Request
Diffs) that need to be downloaded from GCS.

**Solution:** temporarily copy this file from the console node over to the file
node (and delete it again when you are done!)

### Statement timeouts

That can happen because of some non-optimized queries in the current Exporter
code (e.g. <https://gitlab.com/gitlab-org/gitlab/-/issues/212355#note_364049215>).
This needs to get fixed in code probably. Try to get help from the Import team
(#g_manage_import).

### SendTimeoutError

On at least one occasion the export + archive worked fine, but the upload to
GCS failed with:

```
Sending upload query command to https://www.googleapis.com/upload/storage/v1/b/gitlab-gprd-uploads/o?upload_id=REDACTED&upload_protocol=resumable
Upload status active
Sending upload command to https://www.googleapis.com/upload/storage/v1/b/gitlab-gprd-uploads/o?upload_id=REDACTED&upload_protocol=resumable
Error - #<HTTPClient::SendTimeoutError: execution expired>
```

8 times, 4 times each with 2 different values for `REDACTED`.  Given the
archive is written to disk, tar/gzipped, then uploaded, we can bypass the
final upload step, and use `gsutil` and a manual cleanup instead.

WARNING: This use private methods, and is only known to be valid as at this writing
in late Sept 2020, and requires manual cleanup.
You should check the code at app/services/projects/import_export/export_service.rb
and lib/gitlab/import_export/saver.rb to see if this is still valid.  If so, instead
of calling e.execute, run:

```
e.send :save_exporters
saver = Gitlab::ImportExport::Saver.new(exportable:p, shared:p.import_export_shared)
saver.send :compress_and_save
saver.send :archive_file
```

This is roughly what `e.execute` does but without the upload, and then prints the path
to the file that it created.  You are now responsible for copying that archive
somewhere, e.g. as described above in [#no-download-link-and-no-download-email] and you
*MUST* also delete both it and the temporary export directory that was created alongside
the archive, otherwise the root disk on the console server will gradually fill up as
people do this.

## Debugging

### Call exporters one-by-one

The `execute` method of the Exporter actually just [loops over all defined
exporters](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/services/projects/import_export/export_service.rb#L61-66),
so we also can do this manually to see where the error is happening. For each of
the defined exporters:

```ruby
e.send(:version_saver).send(:save)
e.send(:avatar_saver).send(:save)
...
```

To find the location of the generated json and archive files, you can define a
saver:

```ruby
s = Gitlab::ImportExport::Saver.new(exportable: p, shared:p.import_export_shared)
```

This will show you the *export_path*, e.g. something like
`/var/opt/gitlab/gitlab-rails/shared/tmp/gitlab_exports/@hashed/49/94/4994...`.

To try an upload you can run

```ruby
s.send(:compress_and_save)
s.send(:save_upload)
```

Please make sure to delete the created files under `tmp/gitlab_exports/...` when
you are done.
