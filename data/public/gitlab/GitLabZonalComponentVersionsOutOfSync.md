# GitLabZonalComponentVersionsOutOfSync

## Overview

GitLab components are running different versions across zonal clusters in the same environment for longer than expected.

Rolling deploys transiently produce this state, so the alert only fires when the drift persists past the normal deploy window. A sustained firing usually means one of:

- An auto-deploy pipeline is stuck or has failed.
- Maintenance on a zonal cluster paused deployments to it (for example a rebuild or scheduled work).
- A CI job that applies to one cluster failed while others succeeded.

## Services

- [Kubernetes Service Overview](../kubernetes.md)
- Owner: [Fleet Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/fleet-management/)

## Metrics

The alert is defined in [`mimir-rules/gitlab-{gprd,gstg}/kube/kubernetes.yml`](../../../mimir-rules/gitlab-gprd/kube/kubernetes.yml) and compares the `gitlab_version_info` metric across zonal clusters in the same environment.

## Alert Behavior

- Non-paging severity. Visible in Alertmanager and Slack.
- Expected during normal auto-deploys; suppresses itself once versions converge.
- Sustained firings past 1 hour warrant investigation.

## Severities

- Default: `S4`.
- Consider `S3` if drift persists past a full deploy cycle and one cluster is stuck on an older release.

## Verification

1. Check the alert graph to identify which cluster is out of sync.
2. Confirm which version each cluster is running:

    ```sh
    for cluster in gprd-us-east1-{b,c,d}; do
      glsh kube use-cluster "$cluster"
      echo -n "$cluster: "
      kubectl get configmap --namespace gitlab gitlab-gitlab-chart-info -o jsonpath='{.data.gitlabVersion}'
      echo
    done
    ```

3. Compare against the latest successful deploy in the [`#announcements` Slack channel](https://gitlab.enterprise.slack.com/archives/C8PKBH3M5).

## Recent changes

- [Recent auto-deploy pipelines](https://ops.gitlab.net/gitlab-com/gl-infra/deployer/-/pipelines)
- [Recent `k8s-workloads/gitlab-com` MRs](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/merge_requests?scope=all&state=merged)
- [Recent `config-mgmt` MRs](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&state=merged)

## Troubleshooting

1. Check whether auto-deploy is stuck or a CI job failed on the lagging cluster.
2. If a cluster is intentionally skipped (`CLUSTER_SKIP` set in the [`ops` mirror CI vars](https://ops.gitlab.net/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/settings/ci_cd)), silence the alert and remove `CLUSTER_SKIP` when maintenance completes.
3. If Helm is stuck on a cluster, follow [Helm Upgrade is Stuck](../helm-upgrade-stuck.md).
4. Re-run the Kubernetes deploy job for the lagging cluster from the latest successful `auto-deploy` pipeline.

## Escalation

- Delivery / Release Managers if auto-deploy is stuck.
- `#g_fleet_management` for cluster-level issues.

## Definitions

- Alert rule: [`mimir-rules/gitlab-gprd/kube/kubernetes.yml`](../../../mimir-rules/gitlab-gprd/kube/kubernetes.yml)
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kube/alerts/GitLabZonalComponentVersionsOutOfSync.md)

## Related Links

- [Related alerts](./)
- [Kubernetes Service Overview](../kubernetes.md)
- [Helm Upgrade is Stuck](../helm-upgrade-stuck.md)
