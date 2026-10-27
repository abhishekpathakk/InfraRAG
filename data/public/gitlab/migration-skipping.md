# Migration Skipping

Skipping or disabling a Rails migration could be needed if one migration is deemed to cause
a regression on GitLab.com. Instead of reverting the commit that introduced said migration,
we can instruct Rails to never execute it by marking it as already-executed.

A chatops command can be used to achieve the desired result. Run the following in
the `#production` Slack channel (assuming this migration
`db/post_migrate/20200026113518_remove_column_from_table.rb`):

```
/chatops gitlab run migrations mark 20200026113518
```

If the migration is running against the CI database, then add the `--database ci` flag:

```
/chatops gitlab run migrations mark 20200026113518 --database ci
```
