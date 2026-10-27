# Gitaly Stale Locks

## Symptoms

After a Gitaly node is restarted, the rate of "The operation could not be completed. Please try again." errors is elevated.
`error_metadata.error_details` shows "cannot lock references" for RPCs like DeleteRefs.

## Cause

An improper Gitaly shutdown may have left stale ref lock files in the affected repository. When a subsequent request attempts
to modify the reference, Git thinks it is being concurrently updated and produces an error.

## Fix

In most cases, Gitaly's scheduled housekeeping should clean up stale ref lock files. In repositories with a low amount of
write activity, housekeeping may not get the chance to execute.

To address the issue manually:

1. Obtain a list of affected repositories, i.e. `gitlab-org/gitlab`.
2. Obtain access to a production Rails console.
3. Execute the following Ruby snippet to manually execute housekeeping on the affected repositories, replacing `YOUR_REPOS_HERE`
   with a newline-separated list of paths:

```rb
%w[
  YOUR_REPOS_HERE
].each { |path| Gitlab::GitalyClient::RepositoryService.new(Project.find_by_full_path(path).repository).optimize_repository }
```

4. Observe that errors with `error_metadata.error_details` of "cannot lock references" ceases.
