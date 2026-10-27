# Retrying a Failed Patch

You can retry a patch that has failed after verifying that the failure will not repeat when retried.
If the failure was due to something transient, it should be safe to retry.

If the failure was due to CI related flakiness, such as a "runner system failure"
([example](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/jobs/19809358)), you can retry
the failed job itself.

If you would like to start a new pipeline to apply the patch, you can run the command below.
Note that this will add the patch to the back of the queue.

```bash
ringctl patch retry <patch-id> -e <cellsdev|cellsprod>
```

This command will:

- Create a new branch named `retry-<patch-id>`
- Remove the error message and set `in_rollout` to `false`
- Commit the changes to the new branch
- Print a merge request URL for you to create an MR. When the MR is merged, the patch will be re-queued.
