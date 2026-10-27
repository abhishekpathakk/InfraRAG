# Canceling running imports

> **When to use this runbook:** a user (or their project) is generating load through an import, typically during an abuse-driven incident, and you have blocked or are about to block the user.
> **Blocking or banning a user does not stop their imports.**

## Summary

Imports keep running after the user who started them is blocked or banned.

To stop an import, cancel it. Canceling marks the import as `canceled`. Jobs that have not started yet exit when they run, and no further stages are scheduled.

> [gitlab-org/gitlab#631166](https://gitlab.com/gitlab-org/gitlab/-/work_items/631166) tracks canceling imports automatically when a user is blocked or banned.
> Until that change is deployed to GitLab.com, follow the manual steps below. Once it is deployed, use them to verify that the cancel happened.

## What canceling does and does not do

- **Queued jobs stay in Sidekiq.** They exit when they run, so queue depth only drops as they drain.
- **GitHub, Bitbucket Cloud, Bitbucket Server and Direct Transfer imports stop shortly after.** Their workers check the import state between units of work.
- **Repository by URL, manifest, FogBugz, Gitea and file-based imports are not interrupted once running.** Each runs inside a single `RepositoryImportWorker` that does not check the import state after it starts, so a clone or fetch in progress keeps loading Gitaly until it finishes. If the load continues after canceling, find and kill the job, see the [Sidekiq survival guide for SREs](../sidekiq/sidekiq-survival-guide-for-sres.md).
- **Canceling cannot be undone.** The project's `import_data` is deleted and a canceled import cannot be rescheduled, so unblocking the user does not resume it. The partially imported project stays. Deleting it is a separate decision.

## Prerequisites

- Rails console access on GitLab.com, see [granting Rails or DB access](../uncategorized/granting-rails-or-db-access.md).
- The username of the blocked user, or the full path of the project (for example from Gitaly errors or Kibana `json.meta.project`).

## Steps

1. Open a Rails console.

1. List the in-flight imports.

    Project imports (GitHub, Bitbucket, Gitea, FogBugz, file-based, manifest, repository by URL) and [Direct Transfer](./direct-transfer.md) migrations. Set `scope` and `bulk_import_scope` by project or by user:

    ```ruby
    # By project:
    project = Project.find_by_full_path('<namespace/project>')
    scope = ProjectImportState.where(project: project)
    bulk_import_scope = BulkImport.where(id: BulkImports::Entity.where(project_id: project.id).select(:bulk_import_id))

    # By user:
    user = User.find_by_username('<username>')
    scope = ProjectImportState.joins(:project).where(projects: { creator_id: user.id })
    bulk_import_scope = BulkImport.where(user_id: user.id)
    ```

    Then list them:

    ```ruby
    # Pull mirrors share ProjectImportState, so leave them out: canceling also deletes the project's import_data.
    states = scope
      .where(status: %w[scheduled started])
      .preload(:project)
      .to_a
      .reject { |state| state.project.mirror? }

    states.each { |s| puts [s.project.full_path, s.project.import_type, s.status].join("\t") }; nil
    ```

    Direct Transfer migrations:

    ```ruby
    bulk_imports = bulk_import_scope.with_status(:created, :started).to_a

    bulk_imports.each { |b| puts [b.id, b.status_name, b.entities.count].join("\t") }; nil
    ```

1. Cancel them. `cancel` returns `true` when the import was canceled:

    ```ruby
    states.each { |s| puts "#{s.project.full_path}: #{s.cancel}" }; nil

    bulk_imports.each { |b| puts "#{b.id}: #{b.cancel}" }; nil
    ```

    Canceling a `BulkImport` also cancels all its entities.

    `false` means the import was not canceled, for example because it finished after you listed it. Check its status with `reload.status`.

1. Run the listing from step 2 again. It should come back empty. If the load continues, see [what canceling does and does not do](#what-canceling-does-and-does-not-do).

## Related

- [Blocking a project causing high load](../uncategorized/block-high-load-project.md)
- [Importers runbooks](./README.md)
- [Sidekiq survival guide for SREs](../sidekiq/sidekiq-survival-guide-for-sres.md)
