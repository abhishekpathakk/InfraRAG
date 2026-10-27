# Creating Patches

## Creating a Patch

Use the `ringctl patch create` subcommand with the desired operation.

### Basic Examples

Update a single value:

```bash
ringctl patch create replace /instrumentor_version v16.xxx.x -e <cellsdev|cellsprod> --related-to "<issue_url>"
```

Combine multiple operations in one patch:

```bash
ringctl patch create add /use_gar_for_prerelease_image true replace /instrumentor_version v16.xxx.x --related-to <issue_id> --priority <3> -e <cellsdev|cellsprod>
```

Add a complex JSON structure:

```bash
ringctl patch create add "/byod" '{"instance": "gitlab.com"}' --related-to <issue_id> --priority <3> -e <cellsdev|cellsprod>
```

The command will create a Merge Request in [`cells/tissue`](https://ops.gitlab.net/gitlab-com/gl-infra/cells/tissue/). Get it reviewed and merged into `main`. Note the `patch_id` for tracking.

## Priority Settings

> [!note]
> Only one patch can be "In Progress" for a particular ring at any time.
> Patches run sequentially according to their priority.
> For urgent patches, consider setting priority to 3.
