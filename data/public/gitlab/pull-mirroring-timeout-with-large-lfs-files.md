# Pull Mirroring Timeout with Large LFS Files

## Symptoms

A pull mirror timing out in a repository with large Git LFS files is a known issue. In some cases the time to download LFS files exceeds 24 hours, and results in the job eventually being removed as stale.

## Verification

To verify that this is the case:

1. Verify the import is timing out with the following rails console commands:

```ruby
project = Project.find(<project_id>)

project.import_state.status # should equal to `started`
project.import_state.last_error # should equal `Import timed out. Import took longer than x seconds`
```

1. Query Sidekiq logs in Kibana with the following filter: `json.class: "RepositoryUpdateMirrorWorker" AND json.meta.project: "<project_path>"` ([Kibana](https://log.gprd.gitlab.net/app/r/s/E5R17))

1. Use the `json.correlation_id` from (1) to check Gitaly logs with the following filter: `json.correlation_id: "<insert_correlation_id>"` ([Kibana correlation dashboard](https://log.gprd.gitlab.net/app/r/s/tuPA6))

If no errors are present, it's possible to manually synchronize the two repositories to unblock the pull mirroring process.

## Manually Synchronize Repositories

```shell

git clone <source_repository_url>
git remote add mirror <mirror_repository_url>

git push mirror <default_branch>

```
