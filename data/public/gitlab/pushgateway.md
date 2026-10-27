# Push Gateway

## Deployment

We deploy the [pushgateway](https://github.com/prometheus/pushgateway) in a VMs, and we have one for each environment:

- `gprd`: [`blackbox-01-inf-gprd.c.gitlab-production.internal`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/e86dcb5c521eb33c1090119e788681826d760bd4/roles/gprd-base-blackbox.json)
- `gstg`: [`blackbox-01-inf-gstg.c.gitlab-staging-1.internal`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/e86dcb5c521eb33c1090119e788681826d760bd4/roles/gstg-base-blackbox.json)
- `ops`: [`blackbox-01-inf-ops.c.gitlab-ops.internal`](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/e86dcb5c521eb33c1090119e788681826d760bd4/roles/ops-base-blackbox.json)

## How to Delete Metrics

> The Pushgateway never forgets series pushed to it and will expose them to Prometheus forever unless those series are manually deleted via the Pushgateway's API.
>
> [source](https://prometheus.io/docs/practices/pushing/#when-to-use-the-pushgateway)

Imagine a scenario where we want to delete all the metrics for the `job="walg-basebackup"` that have a `type="null"`.

1. SSH inside of the pushgateway VM, and validate that the metric is there.

   ```sh
   $ ssh blackbox-01-inf-gprd.c.gitlab-production.internal

   steve@blackbox-01-inf-gprd.c.gitlab-production.internal:~$ curl -s 127.0.0.1:9091/metrics | grep 'null'
   gitlab_job_failed{instance="",job="walg-basebackup",resource="walg-basebackup",shard="default",tier="db",type="null"} 0
   gitlab_job_max_age_seconds{instance="",job="walg-basebackup",resource="walg-basebackup",shard="default",tier="db",type="null"} 108000
   gitlab_job_start_timestamp_seconds{instance="",job="walg-basebackup",resource="walg-basebackup",shard="default",tier="db",type="null"} 1.723680043e+09
   gitlab_job_success_timestamp_seconds{instance="",job="walg-basebackup",resource="walg-basebackup",shard="default",tier="db",type="null"} 1.723730422e+09
   push_failure_time_seconds{instance="",job="walg-basebackup",shard="default",tier="db",type="null"} 0
   push_time_seconds{instance="",job="walg-basebackup",shard="default",tier="db",type="null"} 1.723730422461835e+09
   ```

1. [Delete](https://github.com/prometheus/pushgateway?tab=readme-ov-file#delete-method) the metrics:

   ```sh
   steve@blackbox-01-inf-gprd.c.gitlab-production.internal:~$ curl -X DELETE http://127.0.0.1:9091/metrics/job/walg-basebackup/tier/db/shard/default/type/null
   ```

   Note the URL will require you to have most of the labels, to target the specific metric. For example above we had to specify the `job`, `tier`, `shard`, and `type` label.
   For more information how to construct the label check [pushgateway documentation](https://github.com/prometheus/pushgateway/blob/d694f612780ad09980d6e9f276f437058d8a5b01/README.md#command-line)

1. Check if metrics are still there:

   ```sh
   steve@blackbox-01-inf-gprd.c.gitlab-production.internal:~$ curl -s 127.0.0.1:9091/metrics | grep 'null'
   steve@blackbox-01-inf-gprd.c.gitlab-production.internal:~$
   ```

   You might also want to validate that it's not longer available on dashboards.
