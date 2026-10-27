# GET Monitoring Setup

This documentation outlines setting up the staging-ref environment to work with GitLab infrastructure monitoring.

## Prerequisites

* A private cluster is prefered for setting up alertmanager.

## Notes

* Staging-ref is not VPC peered environment therefore we had to add workarounds such as [adding an ingress for each alertmanager and configuring Cloud Armor](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-helmfiles/-/merge_requests/551).

  > [!note]
  > The `gitlab-helmfiles` project is archived; services have since migrated to [`argocd/apps`](https://gitlab.com/gitlab-com/gl-infra/argocd/apps).

## Disable built-in GET monitoring

GET sets up Prometheus and Grafana in a VM and the default GitLab Helm chart defaults which enable Prometheus and Grafana. They will not be used and can be disabled. You can view examples of how to do this via the following MRs:

* [Disable Grafana and prometheus managed by GET](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/merge_requests/9/diffs) and remove [GET monitoring VMs](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/merge_requests/43) in the [`gitlab_charts.yml.j2`](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/322ea56bd7529ff4afd38b293c89578fcdf3a337/3k_hybrid_geo/ansible/us-east1/files/gitlab_configs/gitlab_charts.yml.j2) custom helm config used by GET. This can be done by adding the following to the GitLab helm values:

 ```yaml
 global:
   # Disable Grafana
   grafana:
     enabled: false
 ...
 # Disable built-in Prometheus
 prometheus:
   install: false
 ```

## Enable labels

Labels help organize metrics by service. Labels can be added via the GitLab helm chart.

* Labels need to be added to the GitLab helm values:

 ```yaml
 global:
   common:
     labels:
       stage: main
       shard: default
       tier: sv
 ```

* Deployment labels need to be added. For an up-to date list check out [`gitlab_charts.yml.j2`](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/main/3k_hybrid_geo/ansible/us-east1/files/gitlab_configs/gitlab_charts.yml.j2) in the `staging-ref` repository.

## Prometheus

[Prometheus](https://prometheus.io/docs/introduction/overview/) an open-source monitoring and alerting tool used to monitor all services within GitLab infrastructure. You can read more about technical details the project [here](https://prometheus.io/docs/introduction/overview/).

### Deploy `prometheus-stack`

[Prometheus-stack](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/tree/main/3k_hybrid_geo/ansible/us-east1/helm/prometheus-stack) is a helm chart that bundles cluster monitoring with prometheus using the prometheus operator. We'll be using this chart to deploy prometheus.

* Deploy to the GET cluster under the `prometheus` namespace via helm. In staging-ref, this is managed by CI jobs that [validate](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/697ef75e1a81da4942274fce3eacfebce4f50152/.gitlab/ci/.mr_checks.yml#L43-53) and [configure](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/2005cbcc49034513111dd3f9ed842bfba5e9dcc2/.gitlab-ci.yml#L139-145) any changes to the helm chart. You can view the setup of this chart in [this directory](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/tree/main/3k_hybrid_geo/ansible/us-east1/helm/prometheus-stack).

### Scraping targets

Scrape targets are configured in the `values.yaml` file under the `prometheus-stack` directory. Scrape targets are applied relabeling to match what is used in staging and production.

1. Kubernetes targets. Prometheus scrape targets can be found in `additionalPodMonitors` and `additionalServiceMonitors` in [`values.yaml`](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/a57560afd38e55f46676d4848b6f9024cb4ac81a/3k_hybrid_geo/ansible/us-east1/helm/prometheus-stack/values.yaml#L47).

2. Omnibus targets. Prometheus scrape targets can be found under `additionalScrapeConfigs` in [`values.yaml`](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/blob/a57560afd38e55f46676d4848b6f9024cb4ac81a/3k_hybrid_geo/ansible/us-east1/helm/prometheus-stack/values.yaml#L206).

### Exporters

Exporters are "exporting" existing metrics from their applications or services. These are used by prometheus to scrape metrics. A few of them are disabled by default and we'll need to enable them in order to use them. Exporters that need to be enabled manually within the GitLab helm values are:

* gitlab-shell [(merge request example)](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/commit/bb55ac754f937f07eabd6ec3d108094630c4c648)
* http-workhorse-exporter [(merge request example)](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/commit/05b590a610f0853f6eaac567c0a31288d614005f)

## Alerts and Alertmanager

Alerting rules are configured in Prometheus and then it sends alerts to an Alertmanager. The Alertmanager then manages those alerts and sends notifications, such as to a slack channel. We will not be using the bundled Alertmanager in `prometheus-stack`. Instead we've configured the use of existing alertmanager cluster.

Note: If using a public cluster you will need to configure [IP Masquerade Agent](https://kubernetes.io/docs/tasks/administer-cluster/ip-masq-agent/#ip-masquerade-agent-user-guide) in your cluster. [Example configuration](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/tree/ec82942ec2191f47a5653c70220b6328befff7f8/3k_hybrid_geo/ansible/us-east1/helm/ip-masq-agent).

1. Configure Alertmanager

* [Add the cluster IP](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/74a38839b57d326a0ff8ffdf86f61a803890adc5/environments/ops/main.tf#L1294-1296) to the allowed IP ranges used by our [CloudArmor](https://docs.cloud.google.com/armor/docs/configure-security-policies) security policy.

  ```
          src_ip_ranges = [
          "x.x.x.x/32", # GKE cluster NAT IP
        ]

  ```

* Configure `additionalAlertManagerConfigs` ([example merge request](https://gitlab.com/gitlab-org/quality/gitlab-environment-toolkit-configs/staging-ref/-/merge_requests/42/diffs)).

1. Configure Dead Man's Snitch for Alertmanager. Alertmanager should send notifications for the dead man’s switch to the configured notification provider. This ensures that communication between the Alertmanager and the notification provider is working. ([example merge request](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4287))
1. Configure routing to Slack channels ([example merge request](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4281/diffs)).

## Prometheus rules

* TBA.

## Dashboards

Dashboards for staging-ref can be found in Grafana under the [staging-ref folder](https://dashboards.gitlab.net/d/Fyic5Wanz/server-performance?orgId=1). If additional dashboards need to be added they can be added through [the runbooks](https://gitlab.com/gitlab-com/runbooks/-/tree/master/dashboards) or they can be added manually.

If added manually the dashboard `uid` needs to be added to the [protected dashboards list](https://gitlab.com/gitlab-com/runbooks/-/blob/9a4b5c8bc68da6f28bda37c4e30b2bcae499bc9a/dashboards/protected-grafana-dashboards.jsonnet#L50) to prevent automated deletion that happens every 24 hours.
