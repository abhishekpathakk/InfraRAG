# component_saturation_slo_out_of_bounds:kube_persistent_volume_claim_disk_space

## Overview

- This alert means that a Kube persistent volume is running out of disk space.
- This could be natural growth of the data stored within the volume.
- This could also be an abnormality where an unexpectedly large amount of data is being written for some reason.
- This affects the pod(s) that have the full volume. It could cause downtime of thoes pods if the drive fills up.
- The recipient of the alert needs to investigate which volume is filling up, and remediate the issue either via growing the disk or determining why an anomolous amount of data is being written and cleaning the volume.

## Services

- [Kubernetes Service Overview](../kubernetes.md)
- Owner: [Fleet Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/production-engineering/fleet-management/)

## Metrics

- This alert is based on `kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes`.
- The soft SLO is at 85% full and the hard SLO is at 90% full.
- [Example Grafana Query](https://dashboards.gitlab.net/explore?schemaVersion=1&panes=%7B%22pum%22:%7B%22datasource%22:%22mimir-gitlab-gprd%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22max%20by%28environment,%20shard,%20cluster,%20namespace,%20persistentvolumeclaim%29%20%28%5Cn%20%20clamp_min%28%5Cn%20%20%20%20clamp_max%28%5Cn%20%20%20%20%20%20kubelet_volume_stats_used_bytes%5Cn%20%20%20%20%20%20%2F%5Cn%20%20%20%20%20%20kubelet_volume_stats_capacity_bytes%5Cn%20%20%20%20%20%20,%5Cn%20%20%20%20%20%201%29%5Cn%20%20,%5Cn%20%200%29%5Cn%29%5Cn%22,%22range%22:true,%22instant%22:true,%22datasource%22:%7B%22type%22:%22prometheus%22,%22uid%22:%22mimir-gitlab-gprd%22%7D,%22editorMode%22:%22code%22,%22legendFormat%22:%22__auto%22%7D%5D,%22range%22:%7B%22from%22:%22now-1h%22,%22to%22:%22now%22%7D%7D%7D&orgId=1)

## Alert Behavior

- This alert should be fairly rare.
- This alert can be silenced if there is a plan in place to resolve the issue. Generally, the alert should be resolved instead of silenced.

## Severities

- Incidents involving this alert are likely S3 or S4 as the service is likely still up. If a PVC fills up, it could impact the service, but this alert should fire before it is full.
- This is not a user impacting alert.

## Verification

- [Grafana Dashboard](https://dashboards.gitlab.net/d/alerts-sat_kube_pvc_disk_space/e8290dd4-ed63-569b-bc54-5acef4cdbc3f?from=now-6h%2Fm&to=now-1m%2Fm&var-environment=gprd&orgId=1&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-type=ai-assisted&var-stage=main)

## Recent changes

- [Recent change requests](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/?label_name%5B%5D=change)
- [argocd/apps merge requests](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/merge_requests)

## Troubleshooting

- Check the dashboard linked in the alert to determine which PVC is full.
- Once the PVC is identified, check the associated pod logs to see if there is any clear reason the drive is filling up.

## Possible Resolutions

- Increase PVC size — see [k8s-pvc-resize.md](../k8s-pvc-resize.md) for the safe procedure.
- [Zoekt persistent volume claim saturation](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/18220#note_1977890253)
- [Prometheus-agent PVC saturation](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/17660)

## Dependencies

- No other dependencies can cause this alert.

## Escalation

- Slack Channel: #g_runway

## Definitions

- [Alert definition](../../../mimir-rules-jsonnet/saturation.jsonnet)
- It is unlikely we should ever tune this alert much as the thresholds are reasonable percentages.
- [Edit this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/kube/alerts/kube_persistent_volume_claim_disk_space.md)
- [Update the template used to format this playbook](https://gitlab.com/gitlab-com/runbooks/-/edit/master/docs/template-alert-playbook.md)

## Related Links

- [Related alerts](./)
- [Related documentation](../README.md)
