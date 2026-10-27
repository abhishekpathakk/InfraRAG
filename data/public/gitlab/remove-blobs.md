# Remove Blobs

The Remove Blobs feature permanently deletes blobs that contain sensitive or confidential information.

## Sequence

1. Blobs are removed by the `RewriteHistoryWorker` asynchronously in Sidekiq. Job logs can be found in [Kibana](https://log.gprd.gitlab.net/app/r/s/tISLD).

1. `RewriteHistoryWorker` calls `RewriteHistoryService`, which puts the project in a read only state before executing the call to rewrite history. Ongoing pushes to the repository may still go through, potentially causing remove blobs to fail with a `source repository checksum altered` error.

1. This worker calls the `rewrite_history` Gitaly RPC. Gitaly logs can be found using the correlation [dashboard](https://log.gprd.gitlab.net/app/r/s/tuPA6). Use the `correlation_id` found in Sidekiq job logs.

1. After this job completes, objects are left in a dangling state (not attached to any tags or branches). These can be cleaned up by running housekeeping, and pruning unreachable objects. These steps are documented in the Remove Blobs [documentation](https://docs.gitlab.com/user/project/repository/repository_size/#remove-blobs).

## Removing blobs on previously forked projects

A known issue exists when removing blobs for projects that have been previously forked, and the offending blobs are still part of the old object pool.

Diagnostics and a workaround is documented in this [issue](https://gitlab.com/gitlab-org/gitlab/-/issues/537390).

## Contacting the team

Remove Blobs is owned by Create:Source Code Management.

Requests for help can be submitted using the [source code group template](https://gitlab.com/gitlab-com/request-for-help/-/issues/new?description_template=SupportRequestTemplate-SourceCode).

Urgent, or less formal requests can be made directly on Slack in one of our team channels:

* [#g_create_source_code](https://gitlab.enterprise.slack.com/archives/CK75EF2A2) (general)
* [#g_create_source-code-review-fe](https://gitlab.enterprise.slack.com/archives/CS5NHHBJ7) (frontend)
* [#g_create_source_code_be](https://gitlab.enterprise.slack.com/archives/CNU5W2F5M) (backend)
