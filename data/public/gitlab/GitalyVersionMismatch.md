# GitalyVersionMismatch

## Overview

Two or more different version of Gitaly are running in a stage for longer than 60 minutes. This should not be the case as gitaly nodes are expected to run on the same version. It's considered a high-severity issue that requires immediate attention.

During a deployment, two distinct versions of Gitaly may be running alongside one another, but this should not be the case for more than 60m.

## Services

- [Service Overview](../README.md)
- Team that owns the service: [Core Platform:Gitaly Team](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/tenant-scale/gitaly/)
- **Label:** gitlab-com/gl-infra/production~"Service::Gitaly"

## Metrics

- [This expression](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L97) is measuring the count of deployed Gitaly versions in `gprd` environment in different stages. The counter per stage should be equal to 1 under normal conditions
- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L96)

## Alert Behavior

- This alert [should be rare](https://nonprod-log.gitlab.net/app/r/s/omM76), but if it's triggered, needs to be investigated immediately

## Severities

- This alert might create S1 incidents.
- There might be some gitlab.com users impact
- Review [Incident Severity Handbook](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/incident-management/#incident-severity) page to identify the required Severity Level

## Verification

- [Gitaly Service Overview dashboard](https://dashboards.gitlab.net/d/gitaly-main/gitaly3a-overview?orgId=1)
- Verify that [each stage has only one version of Gitaly](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22yah%22:%7B%22datasource%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22count%20by%20%28stage,%20version%29%20%28sum%20by%20%28stage,%20version%29%20%28gitlab_build_info%7Btier%3D%5C%22stor%5C%22,type%3D%5C%22gitaly%5C%22,%20environment%3D%5C%22gprd%5C%22,%20fqdn%21%3D%5C%22%5C%22%7D%29%29%5Cn%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1) deployed

## Recent changes

- [Closed production issues for Gitaly Service](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=all&label_name%5B%5D=Service%3A%3AGitaly&first_page_size=100)

## Troubleshooting

- Check recent deployments or rollbacks in `gprd` environment
- Identify the [prevailing Gitaly version](https://dashboards.gitlab.net/goto/lbWxrAuSg?orgId=1) in the `gprd` environment
- Identify the [nodes having different Gitaly version](https://dashboards.gitlab.net/goto/tIxrr0XIR?orgId=1) deployed in `gprd` environemnt (replace version with the version found in the previous step)
- Verify that [chef-client run normally](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22yah%22:%7B%22datasource%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22sum%20by%20%28fqdn%29%20%28chef_client_last_run_timestamp_seconds%7Benvironment%3D%5C%22gprd%5C%22,%20fqdn%3D%5C%22file-hdd-02-stor-gprd.c.gitlab-production.internal%5C%22%7D%29%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22e58c2f51-20f8-4f4b-ad48-2968782ca7d6%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1) on the affected nodes (replace `fqdn` for the affected nodes). It is expected to run every 30 minutes

## Possible Resolutions

- [Previous GitalyVersionMismatch incidents](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?sort=created_date&state=closed&label_name%5B%5D=Service%3A%3AGitaly&label_name%5B%5D=a%3AGitalyVersionMismatch&first_page_size=100)

## Dependencies

- [failed chef-client runs or failed deployments (rollbacks)](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18088) can cause a gitaly node to fail to apply a required version

## Escalation

For escalation contact the following channels:

- [#g_gitaly](https://gitlab.enterprise.slack.com/archives/C3ER3TQBT)

Alternative slack channels:

- [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N)
- [#infrastructure_platforms](https://gitlab.enterprise.slack.com/archives/C02D1HQRTKQ)

## Definitions

- [Edit this playbook](GitalyVersionMismatch.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related alerts](./)
- [Gitaly Runbook docs](../README.md)
- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/mimir-rules/gitlab-gprd/gitaly/gitaly.yml#L96)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)
