# Exporting projects silently

From time to time, for legal reasons, we are required to export projects without the owner being aware.  Requests for this will come through Legal, and will have suitable looking authorizations (e.g. subpeonas).

While it is possible for an admin to create an export and it won't *email* the owner, it will be visible in the UI while the export exists, and the owner might notice this and infer something is going on.

To avoid this we can do it via the API with some effort. Adjust as necessary if there is only one (or a subset) of projects necessary. Take care around *large* repositories, or large project exports as well.

## Python script method

1. Download [this script](https://gitlab.com/-/snippets/3615502) into a directory. Using your preferred Python environment management method (e.g. `virtualenv`), install the following dependencies: `pip install requests google.cloud.storage`.
1. Create an access token for your admin account on GitLab.com with `api` permissions, and set it to the `GITLAB_TOKEN` env var.
1. Create a throwaway GCS bucket, preferably in a sandbox GCP project.
1. Create a temporary service account and key.
   - This would need the `signBlob` permission and permissions to upload to the bucket. If in doubt, just give the service account admin permissions to the bucket.
1. Download the key and assign the path to it to the `GOOGLE_APPLICATION_CREDENTIALS` env var: `export GOOGLE_APPLICATION_CREDENTIALS=$(readlink -f key.json)`
1. Run ./export_projects_gcs.py --gitlab-group-id <group/namespace_id> --bucket-name <gcs_bucket_name>
   - You may need to make minor modifications to the script if you're targeting a specific user instead of a group (e.g. by using `https://gitlab.com/api/v4/users/{user_id}/projects?page={page}&per_page={per_page}` as the URL).
1. Copy exports from GCS to where SIRT needs these (often they provide a Drive folder).
1. Cleanup
   - [ ] Admin access token
   - [ ] GCS bucket
   - [ ] Service account
   - [ ] Projects (if you downloaded them locally for transfer)

## Go script method

See [this repo](https://ops.gitlab.net/gl-infra/auto-project-export).
