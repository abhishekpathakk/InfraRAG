# Database dump of ops.gitlab.net

The database of ops.gitlab.net is being dumped partially for analytics purposes.
This is done by means of CI schedules that dumps certain tables from the database
host, then restores the dump into another database accessible by the Data team.

As of this writing, the database user used for the dump is named `dumper`. For more
information on the process, please see the README of the [project](https://ops.gitlab.net/gitlab-com/gl-infra/ops-db-dump)
hosting the CI schedules.
