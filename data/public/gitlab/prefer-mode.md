# Container Registry Prefer Mode

## Why GitLab.com uses `enabled: true`

GitLab.com uses `database.enabled: true` and should stay that way. The .com registry has fully migrated to the metadata database.

For detailed documentation on prefer mode mechanics and lockfile behavior, see the [Container Registry metadata database documentation](https://docs.gitlab.com/administration/packages/container_registry_metadata_database/).

## Detection

Check the registry configuration in the deployment manifests. If `database.enabled` is set to `prefer`, change it back to `true`. On .com the database-in-use lockfile is present, so `prefer` starts normally on the database. If `database.enabled` is `false`, pods fail to start with `ErrDatabaseInUse`.

## Revert

1. Change the configuration back to `database.enabled: true`.
2. Perform a rolling restart of registry pods.
3. Verify pods start successfully and report `using the metadata database` in logs.

On .com, `prefer` with the current lockfile state uses the database, so there is no data impact from a `prefer` misconfiguration. The registry was using the database the entire time.

## Escalation

- [g_container_registry](https://gitlab.enterprise.slack.com/archives/CRD4A8HG8)
- [s_package](https://gitlab.enterprise.slack.com/archives/CAGEWDLPQ)
