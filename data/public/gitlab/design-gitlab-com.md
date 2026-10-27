# design.gitlab.com Runbook

## Overview

The `design.gitlab.com` runs Pajamas Design System and contains brand and product design guidelines and UI components for all things GitLab. The project is located in [https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com](https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com). You can read more this system [here](https://handbook.gitlab.com/handbook/product/ux/pajamas-design-system/).

This is an internally developed Rails app which is running an a GKE cluster, using an Auto DevOps deployment configuration. There is no database, and the staging/review databases currently run in pods provisioned by Auto DevOps.

## Setup for On Call

- Read the README file for the [GitLab Services Base](https://ops.gitlab.net/gitlab-com/services-base) project
- Note the location of the [Metrics Dashboards](https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com/-/metrics?environment=269942)
- Note the location of the [CI Pipelines for the infrastructure](https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com) components
- Note the location of the [CI Pipelines for the application](https://gitlab.com/gitlab-org/gitlab-services/design.gitlab.com/-/pipelines) components

For more detailed information on the setup view the [version.gitlab.com runbooks](../version/version-gitlab-com.md).

## Deployment

The application is deployed using Auto DevOps from the [design-gitlab-com](https://gitlab.com/gitlab-org/gitlab-services/design-gitlab-com/) project. It uses a Review/Production scheme with no staging deployment. If deployment problems are suspected, check for [failed or incomplete jobs](https://gitlab.com/gitlab-org/gitlab-services/design-gitlab-com/-/pipelines), and check the [Environments](https://gitlab.com/gitlab-org/gitlab-services/design-gitlab-com/-/environments) page to make sure everything looks reasonable.

## Project

The production deployment of the `design.gitlab.com` application is in the `design-prod` GCP project. The components to be aware of are:

- The kubernetes cluster `design-prod-gke` and its node pool
- Load balancer (provisioned by the k8s ingress)

The review apps are in the `design-staging` GCP project.

## Terraform

This project and its contents are managed by the [GitLab Services](https://gitlab.com/gitlab-com/gl-infra/gitlab-services) project.  Any infrastructure changes to the environment or K8s cluster should be made as an MR there.  Changes will be applied via CI jobs when the MR is merged.  `design-prod` and `design-staging` are represented as [Environments](https://gitlab.com/gitlab-com/gl-infra/gitlab-services/-/environments) in that project.

## Cluster Management

The resources in the cluster, including the KAS agent, namespaces, and service account roles and permissions, are all configured from the [Cluster management project](https://gitlab.com/gitlab-org/gitlab-services/cluster-management)

## Monitoring

Monitoring is currently limited to pingdom alerts.

## Checking the Ingress

> Note: The kubernetes endpoint is protected, so kubectl commands need to be run from google cloud shell. They won't work from a workstation

Switch contexts to the `design-prod-gke` cluster in the `design-prod` project.

Make sure there is at least one ingress controller pod, and that it hasn't been restarting. Note the age in the last field.

```shell
$ kubectl get pods -n gitlab-managed-apps | grep ingress-nginx-ingress-controller
gitlab-managed-apps                     ingress-nginx-ingress-controller-85ff56cfdd-cjd9b            1/1     Running     0          20h
gitlab-managed-apps                     ingress-nginx-ingress-controller-85ff56cfdd-fmqnh            1/1     Running     0          20h
gitlab-managed-apps                     ingress-nginx-ingress-controller-85ff56cfdd-tg77w            1/1     Running     0          42h
```

Check for Events:

```shell
kubectl describe deployment -n gitlab-managed-apps ingress-nginx-ingress-controller
```

 The bottom of this output will show health check failures, pod migrations and restarts, and other events which might effect availability of the ingress. `Events: <none>` means the problem is probably elsewhere.

## Certificates

Certificates are managed by the `cert-manager` pod installed CI in the cluster management project.  It is configured with [this helmfile](https://gitlab.com/gitlab-org/gitlab-services/cluster-management/-/blob/main/helmfile.yaml)

### Resources

The overall usage can be checked like this:

```shell
$ kubectl top nodes
NAME                                            CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
gke-design-prod-gke-node-pool-0-58e08e59-popj   132m         1%     3183Mi          11%
gke-design-prod-gke-node-pool-0-870e91bf-n1jh   125m         1%     2534Mi          9%
gke-design-prod-gke-node-pool-0-b4ecf86b-qhl6   178m         2%     1705Mi          6%
```

Pods can be checked like this:

```shell
$ kubectl top pods -n design-prod
NAME                          CPU(cores)   MEMORY(bytes)
production-5f476b4f58-6jlb4   1m           10Mi
production-5f476b4f58-gjb7b   1m           10Mi
production-5f476b4f58-ql6jv   1m           10Mi
```

### Alerting

Currently, the only alerting is the pingdom blackbox alerts.  This is the same as what was set up in the previous AWS environment, but probably needs to be improved.  The preference is to use built in GitLab functionality where possible.
