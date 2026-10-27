# Complete zonal failure recovery procedure

## Experiment

The steps for the experiment are included in the change_zonal_recovery [template](https://gitlab.com/gitlab-com/gl-infra/production/-/blob/master/.gitlab/issue_templates/change_zonal_recovery.md)

## Agenda

- An understanding of the [canary stage](https://gitlab.com/gitlab-org/release/docs/-/blob/master/general/deploy/canary.md#overview) is useful. During the gameday we disable canary and this may cause some disruptions to deployments.

## Procedure

- Declare a change issue on slack in the [#production](https://gitlab.enterprise.slack.com/archives/C101F3796) channel by running the following command
  - `/change declare` and select the `change_zonal_recovery` template to create the gameday change issue.
