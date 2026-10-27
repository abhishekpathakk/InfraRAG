# component_saturation_slo_out_of_bounds:kube_persistent_volume_claim_inodes

## Overview

- This alert means that a Kube persistent volume is running out of **inodes** — the number of files it can hold — which is independent of how much disk space is free.
- A volume can exhaust inodes while still reporting plenty of free space. `df -h` will look healthy while `df -i` is at 100%.
- This is usually caused by a workload accumulating a very large number of small files: per-branch or per-MR scratch clones, dependency/module caches, WAL or index files.
- This affects the pod(s) mounting the volume. Once inodes are exhausted, any attempt to create a file fails with `ENOSPC` ("no space left on device") **even though space remains**, which is a misleading error to debug from cold.
- The recipient needs to identify which PVC is saturated, then decide between cleaning up accumulated files, bounding the growth, or growing the volume. Prefer bounding the growth — see [Possible Resolutions](#possible-resolutions).

## Services

- [Kubernetes Service Overview](../README.md)
- Owner: [Runway](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/team/foundations/)

## Metrics

- This alert is based on `kubelet_volume_stats_inodes_used / kubelet_volume_stats_inodes`.
- The soft SLO is at 85% and the hard SLO is at 90%.
- [Example Grafana Query](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22pum%22:%7B%22datasource%22:%22mimir-gitlab-ops%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22max%20by%20(environment,%20shard,%20cluster,%20namespace,%20persistentvolumeclaim)%20(%5Cn%20%20clamp_min(%5Cn%20%20%20%20clamp_max(%5Cn%20%20%20%20%20%20kubelet_volume_stats_inodes_used%5Cn%20%20%20%20%20%20%2F%5Cn%20%20%20%20%20%20kubelet_volume_stats_inodes%5Cn%20%20%20%20%20%20,%5Cn%20%20%20%20%20%201)%5Cn%20%20,%5Cn%20%200)%5Cn)%5Cn%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-ops%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-6h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)

> [!IMPORTANT]
> **Match the datasource to the alert's `env` label before querying.** The alert
> payload carries a `grafana_datasource_id` annotation naming the right tenant —
> `mimir-gitlab-ops` for `env="ops"`, `mimir-gitlab-gprd` for `env="gprd"`. The ops
> tenant is not queried by default in some tooling, and querying the wrong tenant
> returns *no matching series*, which reads like missing data rather than a wrong
> datasource.

## Alert Behavior

- The alerting rule aggregates by `env`, `environment` and `shard`, so **the alert
  itself does not name the PVC**. The saturation detail dashboard does break it down
  per-claim (`resourceLabels: ['persistentvolumeclaim']`) — use the dashboard or the
  raw kubelet query above to identify it.
- Growth is often a **step function** rather than a drift: each step is one unit of
  work (a plan, a build, a compaction) creating a batch of files. Reading the steps
  and correlating them to timestamps on disk is usually the fastest route to the cause.
- This alert can be silenced if there is a plan in place to resolve the issue.
  Generally it should be resolved instead of silenced. Note that a *capacity* silence
  on an unbounded-growth problem tends to recur — see [INC-8304](https://app.incident.io/gitlab/incidents/8304).

## Severities

- Incidents involving this alert are likely S3 or S4 — the service is still up, and
  the alert fires before exhaustion.
- This is not normally a user impacting alert. Assess what the owning workload does:
  for internal tooling (Atlantis, CI) the impact is blocked automation rather than
  customer traffic.

## Verification

- [Grafana Dashboard (ops)](https://dashboards.gitlab.net/d/alerts-sat_kube_pvc_inodes/alerts-kube_persistent_volume_claim_inodes-saturation-detail?from=now-6h&to=now&var-environment=ops&var-type=kube&var-stage=main)
- Confirm on the pod itself, which also tells you whether it is inode-bound or space-bound:

  ```shell
  kubectl -n <namespace> exec <pod> -- df -i <mount>   # inodes
  kubectl -n <namespace> exec <pod> -- df -h <mount>   # bytes
  ```

## Recent changes

- [Recent change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name%5B%5D=change)
- [argocd/apps merge requests](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests)

## Troubleshooting

1. **Identify the PVC** from the dashboard or the raw kubelet query, remembering to
   use the tenant matching the alert's `env`. To list every claim over a threshold:

   ```
   topk(15, kubelet_volume_stats_inodes_used / kubelet_volume_stats_inodes) > 0.8
   ```

2. **Confirm it is inodes, not bytes** with `df -i` and `df -h` on the owning pod. If
   bytes are also high, treat it as
   [kube_persistent_volume_claim_disk_space](kube_persistent_volume_claim_disk_space.md)
   instead.

3. **Find where the inodes are.** With GNU coreutils available, one pass lands on the
   directory holding them, since `--separate-dirs` counts each directory's own entries
   rather than its subtree:

   ```shell
   du --inodes --separate-dirs --one-file-system <mount> | sort -h | tail -20
   ```

   Many images ship busybox, whose `du` has no `--inodes` and whose `find` has no
   `-printf`. There, count per top-level directory and descend into whichever dominates:

   ```shell
   for d in <mount>/*; do printf "%10s %s\n" "$(find "$d" -xdev | wc -l)" "$d"; done
   ```

   > [!NOTE]
   > Steps 2 and 3 assume you can `exec` into the pod. Distroless and scratch images have
   > no shell, so attach an ephemeral container carrying the tools and mount the same
   > volume into it:
   >
   > ```shell
   > kubectl -n <namespace> get pod <pod> -o jsonpath='{.spec.volumes[*].name}'
   > kubectl debug -n <namespace> -it <pod> --image=debian \
   >   --custom=<(echo 'volumeMounts: [{name: <volume>, mountPath: /vol}]')
   > du --inodes --separate-dirs --one-file-system /vol | sort -h | tail -20
   > ```
   >
   > `--custom` is GA from Kubernetes 1.32 and our clusters run 1.35. Use an image with GNU
   > coreutils, busybox and alpine `du` have no `--inodes`. See
   > [k8s-oncall-setup.md](../k8s-oncall-setup.md#pod-access).

4. **Establish whether it is accumulation or undersized provisioning.** Divide used
   bytes by used inodes to get the average file size. On a volume formatted at the ext4
   default of one inode per 16 KiB, inodes run out once byte utilisation reaches roughly
   `average file size / 16 KiB` — so a 4 KiB average exhausts inodes at ~25% full, and an
   8 KiB average at ~50%. Compute it from the observed average rather than assuming a
   fraction; it tells you how much byte headroom will still be free when writes start
   failing, which is what makes `ENOSPC` confusing.

5. **Correlate the steps to timestamps on disk.** `ls -ld` on the candidate
   directories maps each step in the graph to the work that created it.

> [!WARNING]
> Prefer **mtime** over **atime** when judging staleness, and avoid `find` over the
> whole tree if you intend to use atime afterwards. Walking a tree updates atime on
> everything you touch, which destroys the evidence and would defeat any atime-based
> cleanup for its full window.

## Possible Resolutions

- **Bound the growth.** If the volume accumulates scratch data that is safely
  regenerable, add a garbage collector rather than capacity. This is the durable fix.
- **Clean up accumulated files**, once you have confirmed what is safe to remove.
  Regenerable caches and scratch clones usually are; check for in-flight work first.
  `chmod -R u+rwX` the tree first if removal hits `Permission denied` — a file cannot be
  unlinked without write permission on its parent directory, and Terraform copies module
  sources with their original permissions.
- **Grow the PVC** — [k8s-pvc-resize](../k8s-pvc-resize.md). Growing an ext4 volume adds
  block groups and therefore inodes, so this does raise the inode budget. Persist the
  new size in GitOps or it will revert.

  > [!NOTE]
  > Resizing does not change the growth rate. Identify the growth mechanism first — a
  > volume resized without one identified will saturate again.

- Previous incidents:
  - [INC-13112](https://app.incident.io/gitlab/incidents/13112) — Atlantis per-MR workspaces accumulating; `.terraform/modules` copied once per module block
  - [INC-8304](https://app.incident.io/gitlab/incidents/8304) — same PVC resized 10Gi to 20Gi without identifying the cause; recurred five months later
  - [INC-7429](https://app.incident.io/gitlab/incidents/7429) — Atlantis PVC in ops, disk space rather than inodes

## Dependencies

- No other dependencies can cause this alert.

## Escalation

- Slack Channel: #g_runway
- For Atlantis instances specifically, the workload owner is the team owning the
  repository that instance serves.

## Definitions

- [Alert definition](https://gitlab.com/gitlab-com/runbooks/-/blob/master/libsonnet/saturation-monitoring/kube_persistent_volume_claim_inodes.libsonnet)
- It is unlikely we should ever tune this alert much as the thresholds are reasonable percentages.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kube/alerts/kube_persistent_volume_claim_inodes.md?ref_type=heads)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md?ref_type=heads)

## Related Links

- [Related alerts](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/kube/alerts)
- [Related documentation](https://gitlab.com/gitlab-com/runbooks/-/tree/master/docs/kube)
- [Filesystem inode troubleshooting (host-level)](../../monitoring/filesystem_alerts_inodes.md)
