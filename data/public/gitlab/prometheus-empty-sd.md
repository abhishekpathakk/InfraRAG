# Prometheus Empty Service Discovery

## Symptoms

Prometheus has one or more jobs with empty target lists.

## Possible checks

Check to see if there are problems with the service discovery method.

For `file_sd_configs`, check to see if there is a problem with Chef generating the target file.

There may also be jobs that are obsolete and need to be removed.

## Resolution

Fix the SD method or remove the job from the config.

## Job Definitions

Prometheus jobs are defined via chef and can be found on the Prometheus server's `/opt/prometheus/prometheus/prometheus.yml` configuration file.

The following example shows the gitlab-workhorse-web job configuration and it's corresponding [job definition](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-infra-prometheus-server-app.json#L116-120) on the chef-repo.

```
prometheus-app-01-inf-gprd.c.gitlab-production.internal:~$ sudo grep -A 5 gitlab-workhorse-web /opt/prometheus/prometheus/prometheus.yml
- job_name: gitlab-workhorse-web
  honor_labels: true
  file_sd_configs:
  - files:
    - "/opt/prometheus/prometheus/inventory/gitlab-workhorse-web.yml"
```
