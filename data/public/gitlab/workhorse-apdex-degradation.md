# Workhorse Apdex Degradation

A decrease in the [workhorse SLI apdex](https://dashboards.gitlab.net/goto/1RE_jxYNg?orgId=1) can indicate increased Rails page load times.

## Troubleshooting

- Check if the decrease is caused by a specific route by [querying request duration per route](https://dashboards.gitlab.net/goto/_GUJqxLHR?orgId=1).
- Can the decrease in apdex be be linked with a deployment?
- Can the decrease in apdex be correlated with a [feature flag change](https://gitlab.com/gitlab-com/gl-infra/feature-flag-log/-/issues/?sort=created_date&state=closed&label_name%5B%5D=host%3A%3Agitlab.com&first_page_size=50)?
- Checking stage group dashboards for a correlation can narrow down a responsible stage.

## Suspicious Traffic

- Checking the distribution of `json.remote_ip` in long running requests ([Kibana](https://log.gprd.gitlab.net/app/r/s/n9Sfy)) can reveal malicious traffic as the cause of a degraded apdex. Offending IP addresses can then be blocked.
