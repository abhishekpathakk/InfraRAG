# Databasebase backup health check

## Experiment

Stop running the daily database backups verification pipeline.

## Agenda

- Revisit how database backups work.
  - [postgresql-backups-wale-walg](../../patroni/postgresql-backups-wale-walg.md)
  - <https://ops.gitlab.net/gitlab-com/gl-infra/gitlab-restore/postgres-gprd>
- Discuss hypothesis

## Hypothesis

The engineer on call should get paged that there was no backup in the past days.

## Preparation

1. Create issue in <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/new>
1. Identify and inform the SRE on-call during that day running gameday.
