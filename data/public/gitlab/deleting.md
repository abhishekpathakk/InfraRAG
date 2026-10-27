# Deleting a Patch

> [!warning]
> A patch in the "in rollout" state cannot be stopped, as the Instrumentor stages pipeline is already running.

## Delete a patch in the `pending` status

```bash
ringctl patch delete <patch_id> -e <cellsdev|cellsprod>
```

## Delete a patch in the `failed` status

A failed patch might have been partially applied, so we need to revert the patch along with deleting the failed patch.

### Using `ringctl patch invert` (Recommended)

The `ringctl patch invert` command automates the entire reversion process:

```bash
ringctl patch invert <patch_id> -e <cellsdev|cellsprod> --priority N
```

This command will:

- Find the commit that applied the original patch
- Extract the previous attribute values from git history
- Delete the failed patch
- Create a new invert patch with the previous values
- Set an appropriate priority to ensure the invert patch executes first, defaults to 1 (highest priority)
- Target only the ring where the original patch failed (both `ring` and `delete_after_ring` are set to the failed ring)

#### Options

| Flag | Description |
| ---- | ----------- |
| --dry-run | The dry run option is used to preview what the invert patch would contain without making any changes |
| --priority N | This is used to set a priority to ensure the invert is performed before any other actions, if left blank it defaults to 1 the highest priority |

#### Example usage

```bash
# preview the operation
ringctl patch invert 01KB1Y8GJFWMRYZNGGR22BQBGT -e cellsdev --dry-run

# Execute the invert
ringctl patch invert 01KB1Y8GJFWMRYZNGGR22BQBGT -e cellsdev
```

The command creates a merge request containing both the deletion of the failed patch and the new invert patch.

#### Limitations

`ringctl patch invert` command currently only covers `replace` JSON Patch operations. Additional operations will be added as part of <https://gitlab.com/gitlab-com/gl-infra/delivery/-/work_items/21682>

### Manual process (Reference)

If you need to understand what `patch invert` does under the hood, or if you encounter a scenario not covered by the command, you can follow the manual invert process as outlined below:

> [!note]
> If you encounter a scenario not covered by `ringctl patch invert`, please [create an issue](https://gitlab.com/gitlab-com/gl-infra/delivery/-/issues/new) so we can improve the command.

Make the following changes in a single MR:

1. Delete the failed patch

   ```bash
   ringctl patch delete <patch_id> -e <cellsdev|cellsprod>
   ```

   This will create a branch on the remote and commit to it. Push the following changes to the same branch.

1. Introduce a new patch reverting the attribute(s) that were changed in the failed patch to its previous value. You
   can determine the previous value of the attribute(s) by looking at the commit that applied the patch to the ring
   ([example](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/-/commit/e732a450bbae3100ea1a12268ee3f4c89f36bf09)).

   Make sure you set the following attributes correctly:

   - Set the `ring` key in the new patch to the same ring where the previous patch failed.

   - Set the `completed_after_ring` key in the new patch to the same value as the `ring` key, so that the new patch
     is only applied to the ring where the previous patch failed.

   - Set a higher priority for the new patch, so that it is executed first, before any patches that are already in the queue.
     For example, if the first patch in the queue has a priority of 4, set the priority of the new patch to 3, so that it is
     placed at the front of the queue.

## For an auto-deploy patch

For a patch that modifies only `prerelease_version` and has `only_gitlab_upgrade: true`:

- **If the next patch in the queue is also an auto-deploy patch**: It is safe to just delete the failed patch file.
- **Otherwise**: Use [`ringctl rollback`](../auto-deploy.md#rollbacks) to rollback to the previous successful auto-deploy version.
