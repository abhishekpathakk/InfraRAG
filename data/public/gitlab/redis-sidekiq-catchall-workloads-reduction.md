# Redis-Sidekiq catchall workloads reduction

To reduce the load on Redis-Sidekiq from the number of catchall workloads,

## For VMs

`ssh sidekiq-catchall-XX-sv-gprd.c.gitlab-production.internal`

There, invoke: `sudo gitlab-ctl stop sidekiq`

Needs may vary. There are 7 virtual machines which is likely overkill right now even at peaks, but at quiet times we can get away with only 1 active.  Adjust how many are running as necessary (keep an eye on queues in general).  Restart with the hopefully intuitive: `sudo gitlab-ctl start sidekiq`

## For K8S

Establish a secure shell session to the production console system: `ssh console-01-sv-gprd.c.gitlab-production.internal`

There, invoke: `kubectl config get-contexts`

You will be prompted for confirmation, and asked to provide an incident number for reference.

Ensure the selector mark (`*`) is beside `gke_gitlab-production_us-east1_gprd-gitlab-gke` (the regional cluster), not one of the 3 zonal clusters.

If it is not, then you must command it to be selected using: `kubectl config use-context gke_gitlab-production_us-east1_gprd-gitlab-gke`

Next, invoke: `kubectl -n gitlab edit hpa/gitlab-sidekiq-catchall-v1`

Find the `maxReplicas` line, and reduce it.

Default, or git version, is `175`, and we have had good success at `100` with reducing load but not having too much of a backlog.  The `70` target was too low at one point, but `80` was ok at quiet times.  YMMV, season to taste.

Most important is ensuring `maxReplicas` is adjusted back to the same version as in git once we're done, so that automated processes don't tromp over it or get confused.  Ensure you engage with Delivery (Graeme in particular) so that they know that auto deploys may be interrupted/broken, and perhaps to review the status of helm once configuration is restored to normal.

### Tags

To enhance findability, here are some keywords.

redis, redis-sidekiq, catchall, workloads, k8s, kubernetes, VMs, virtual machines, gke,
