# Cloud SQL Restore Pipeline Troubleshooting

## `NoRestorePipelineStarted` alert

This alert fires when no pipeline has ran in the past 24 hours. Check the GitLab project's scheduled pipeline to verify if the pipeline was triggered.

For example, the scheduled pipeline page of
[runway-db-example-production-us-east1](https://ops.gitlab.net/gitlab-com/gl-infra/platform/runway/cloudsql_backups_validation/runway-db-example-production-us-east1/-/pipeline_schedules) would reflect the
status of the `Run restore validation pipeline` pipeline.

## `RestorePipelineNotSuccessful` alert

This alert fires when a pipeline starts but did not complete within 2 hours. This could be due to an actual failure (restore failure or data validation failure) or
a slow pipeline. Depending on the nature of the issue, a pipeline rerun could resolve the problem.

Contact Runway members in the `#g_runway` Slack channel if required.
