## Summary

This document tracks the subnet allocation across multiple infrastructure
projects related to GitLab.com. Any project that requires centralized monitoring
or maintenance from ops runners should be configured to not overlap with the
gitlab-ops project for network peering.

* This doc replaces the previous [tracking spreadsheet on google docs](https://docs.google.com/spreadsheets/d/1l-Oxx8dqHqGnrQ23iVP9XGYariFGPFDuZkqFj4KOe5A/edit#gid=0)
* All environments listed on the [handbook environments page](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/environments/) are covered here

## Reserving a new subnet

* Update this MR with a new allocation, pick a row that has `AVAILABLE GCP`, if
  needed we can start using previously allocated subnets for Azure
* Larger subnets can be split into smaller ones, if necessary

## Subnet Allocations

| First IP        | Last IP            | Subnet           | Project                        | Description
| --------------  | -----------------  | ---------------  | -----------------------------  | ------------------------------
| `10.0.0.0`      | `10.0.255.255`     | `10.0.0.0/16`    | N/A                            | RESERVED
| `10.1.0.0`      | `10.1.3.255`       | `10.1.0.0/22`    | N/A                            | RESERVED
| `10.1.4.0`      | `10.1.4.255`       | `10.1.4.0/24`    | N/A                            | RESERVED
| `10.1.5.0`      | `10.1.5.255`       | `10.1.5.0/24`    | gitlab-ci Runner Managers      | CI
| `10.1.6.0`      | `10.1.7.255`       | `10.1.6.0/23`    | N/A                            | RESERVED
| `10.1.8.0`      | `10.1.15.255`      | `10.1.8.0/21`    | N/A                            | RESERVED
| `10.1.16.0`     | `10.1.31.255`      | `10.1.16.0/20`   | N/A                            | RESERVED
| `10.1.32.0`     | `10.1.63.255`      | `10.1.32.0/19`   | N/A                            | RESERVED
| `10.1.64.0`     | `10.1.127.255`     | `10.1.64.0/18`   | N/A                            | RESERVED
| `10.1.128.0`    | `10.1.255.255`     | `10.1.128.0/17`  | N/A                            | RESERVED
| `10.2.0.0`      | `10.3.255.255`     | `10.2.0.0/15`    | N/A                            | RESERVED
| `10.4.0.0`      | `10.7.255.255`     | `10.4.0.0/14`    | N/A                            | RESERVED
| `10.8.0.0`      | `10.9.255.255`     | `10.8.0.0/15`    | N/A                            | RESERVED
| `10.10.0.0`     | `10.10.7.255`      | `10.10.0.0/21`   | gitlab-ci Ephemeral Runners    | CI-plan-free-7
| `10.10.8.0`     | `10.10.15.255`     | `10.10.8.0/21`   | gitlab-ci Ephemeral Runners    | CI-plan-free-6
| `10.10.16.0`    | `10.10.23.255`     | `10.10.16.0/21`  | gitlab-ci Ephemeral Runners    | CI-plan-free-5
| `10.10.24.0`    | `10.10.31.255`     | `10.10.24.0/21`  | gitlab-ci Ephemeral Runners    | CI-plan-free-4
| `10.10.32.0`    | `10.10.39.255`     | `10.10.32.0/21`  | gitlab-ci Ephemeral Runners    | CI-plan-free-3
| `10.10.40.0`    | `10.10.47.255`     | `10.10.40.0/21`  | gitlab-ci Ephemeral Runners    | CI private (old)
| `10.10.48.0`    | `10.10.55.255`     | `10.10.48.0/21`  | gitlab-ci Ephemeral Runners    | CI shared-gitlab-org
| `10.10.56.0`    | `10.10.63.255`     | `10.10.56.0/21`  | N/A                            | RESERVED
| `10.10.64.0`    | `10.10.79.255`     | `10.10.64.0/20`  | gitlab-ci Temp Priv Runners    | CI private temp
| `10.10.80.0`    | `10.10.95.244`     | `10.10.80.0/20`  | gitlab-ci Ephemeral Runners    | CI private (new)
| `10.10.96.0`    | `10.10.127.255`    | `10.10.96.0/19`  | N/A                            | RESERVED
| `10.10.128.0`   | `10.10.255.255`    | `10.10.128.0/17` | N/A                            | RESERVED
| `10.11.0.0`     | `10.11.255.255`    | `10.11.0.0/16`   | N/A                            | RESERVED
| `10.12.0.0`     | `10.15.255.255`    | `10.12.0.0/14`   | N/A                            | RESERVED
| `10.16.0.0`     | `10.16.255.255`    | `10.16.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-s-amd64 us-east5 (`saas-l-s-amd64-us-east5-0`, shared by all of the shard's projects). Also the Private Services Access range of the gitlab-ops `ops` network, which is not peered with ci
| `10.17.0.0`     | `10.17.255.255`    | `10.17.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-p-amd64 us-east5 (`saas-l-p-amd64-us-east5-0`, shared by all of the shard's projects)
| `10.18.0.0`     | `10.18.255.255`    | `10.18.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-m-amd64 us-east5 (`saas-l-m-amd64-us-east5-0`, shared by all of the shard's projects)
| `10.19.0.0`     | `10.19.207.255`    | N/A              | N/A                            | RESERVED for runner cross-region fallback subnets (`10.19.0.0/17`, `10.19.128.0/18`, `10.19.192.0/20`)
| `10.19.208.0`   | `10.19.223.255`    | `10.19.208.0/20` | gitlab-ci                      | Private Services Access range of the `default` network (not peered with ci)
| `10.19.224.0`   | `10.19.255.255`    | `10.19.224.0/19` | N/A                            | RESERVED for runner cross-region fallback subnets
| `10.20.0.0`     | `10.20.255.255`    | `10.20.0.0/16`   | AWS r-saas-m-staging           | macOS staging jobs VPC, HA VPN to ci
| `10.21.0.0`     | `10.21.255.255`    | `10.21.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-l-amd64 us-east5 (`saas-l-l-amd64-us-east5-0`, shared by all of the shard's projects)
| `10.22.0.0`     | `10.22.255.255`    | `10.22.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-xl-amd64 us-east5 (`saas-l-xl-amd64-us-east5-0`, shared by all of the shard's projects)
| `10.23.0.0`     | `10.23.255.255`    | `10.23.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-2xl-amd64 us-east5 (`saas-l-2xl-amd64-us-east5-0`, shared by all of the shard's projects)
| `10.24.0.0`     | `10.24.255.255`    | `10.24.0.0/16`   | gitlab-ci Ephemeral Runners    | CI saas-l-m-org us-east5 (`saas-l-m-org-us-east5-0`, shared by all of the shard's projects)
| `10.25.0.0`     | `10.29.255.255`    | N/A              | N/A                            | RESERVED for runner cross-region fallback subnets (`10.25.0.0/16`, `10.26.0.0/15`, `10.28.0.0/15`)
| `10.30.0.0`     | `10.30.255.255`    | `10.30.0.0/16`   | AWS r-saas-m-m1                | macOS m1 jobs VPC, HA VPN to ci
| `10.31.0.0`     | `10.31.255.255`    | `10.31.0.0/16`   | N/A                            | RESERVED for runner cross-region fallback subnets
| `10.32.0.0`     | `10.32.255.255`    | `10.32.0.0/16`   | N/A                            | N/A
| `10.34.0.0`     | `10.34.255.255`    | `10.34.0.0/16`   | gitlab-vault                   | Vault and Vault-nonprod GKE
| `10.35.0.0`     | `10.35.255.255`    | `10.35.0.0/16`   | DR testing                     | DR testing
| `10.36.0.0`     | `10.36.255.255`    | `10.36.0.0/16`   | SnowPlow, DR testing           | AWS-SnowPlow, DR testing
| `10.37.0.0`     | `10.37.255.255`    | `10.37.0.0/16`   | DR testing                     | DR testing
| `10.38.0.0`     | `10.38.255.255`    | `10.38.0.0/16`   | N/A                            | N/A
| `10.39.0.0`     | `10.39.255.255`    | `10.39.0.0/16`   | N/A                            | N/A
| `10.40.0.0`     | `10.40.255.255`    | `10.40.0.0/16`   | AWS r-saas-m-l-m2pro           | macOS m2pro jobs VPC, HA VPN to ci
| `10.44.0.0`     | `10.45.255.255`    | `10.44.0.0/15`   | gitlab-ci Experimental Runners | Experimental runners subnets
| `10.46.0.0`     | `10.46.255.255`    | `10.46.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-ops-gke subnet (`10.46.0.0/20` nodes, `10.46.16.0/20` services for runner-managers-ops-1)
| `10.47.0.0`     | `10.47.255.255`    | `10.47.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-ops-gke pods, runner-managers-ops-1 (32 pods per node, a `/26` each, 1024 nodes)
| `10.50.0.0`     | `10.50.255.255`    | `10.50.0.0/16`   | gitlab-ci GKE Runners          | saas-l-p-amd64 network runner-workloads subnet (`10.50.0.0/20` nodes, `10.52.0.0/20` services for the runner-workloads cluster in project 1)
| `10.51.0.0`     | `10.51.255.255`    | `10.51.0.0/16`   | gitlab-ci GKE Runners          | saas-l-p-amd64 network runner-workloads pods, project-1 cluster (16 pods per node, a `/27` each, 2048 nodes)
| `10.52.0.0`     | `10.52.255.255`    | `10.52.0.0/16`   | gitlab-ci GKE Runners          | see `10.50.0.0/16`: services ranges for saas-l-p-amd64 clusters
| `10.58.0.0`     | `10.58.255.255`    | `10.58.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-gke subnet (`10.58.0.0/20` nodes, `10.58.16.0/20` services for runner-managers-gprd-1)
| `10.59.0.0`     | `10.59.255.255`    | `10.59.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-gke pods, runner-managers-gprd-1 (32 pods per node, a `/26` each, 1024 nodes)
| `10.60.0.0`     | `10.60.255.255`    | `10.60.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-gstg-gke subnet (`10.60.0.0/20` nodes, `10.60.16.0/20` services for runner-managers-gstg-1)
| `10.61.0.0`     | `10.61.255.255`    | `10.61.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-gstg-gke pods, runner-managers-gstg-1 (32 pods per node, a `/26` each, 1024 nodes)
| `10.62.0.0`     | `10.62.255.255`    | `10.62.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-dev-gke subnet (`10.62.0.0/20` nodes, `10.62.16.0/20` services for runner-managers-dev-1)
| `10.63.0.0`     | `10.63.255.255`    | `10.63.0.0/16`   | gitlab-ci GKE Runner Managers  | ci network runner-managers-dev-gke pods, runner-managers-dev-1 (32 pods per node, a `/26` each, 1024 nodes)
| `10.64.0.0`     | `10.95.255.255`    | `10.64.0.0/11`   | gitlab-production              | GKE pods
| `10.96.0.0`     | `10.127.255.255`   | `10.96.0.0/11`   | gitlab-staging                 | GKE pods
| `10.128.0.0`    | `10.159.255.255`   | `10.128.0.0/11`  | gitlab-pre                     | GKE pods
| `10.160.0.0`    | `10.163.255.255`   | `10.160.0.0/14`  | gitlab-analysis                | GKE pods
| `10.164.0.0`    | `10.167.255.255`   | `10.164.0.0/14`  | gitlab-analysis                | GKE pods
| `10.168.0.0`    | `10.175.255.255`   | `10.168.0.0/13`  | gitlab-ops                     | GKE pods
| `10.176.0.0`    | `10.176.255.255`   | `10.176.0.0/16`  | gitlab-staging-db              | **Repeatable db provisioning**
| `10.177.0.0`    | `10.177.255.255`   | `10.177.0.0/16`  | gitlab-production-db           | **Repeatable db provisioning**
| `10.178.0.0`    | `10.178.255.255`   | `10.178.0.0/16`  | gitlab-sandbox-db              | **Repeatable db provisioning**
| `10.181.0.0`    | `10.181.255.255`   | `10.181.0.0/16`  | gitlab-analysis-staging        | Analysis Staging GCP
| `10.182.0.0`    | `10.182.255.255`   | `10.182.0.0/16`  | gitlab-ops                     | Ops us-central1 GKE pods
| `10.183.0.0`    | `10.183.255.255`   | `10.183.0.0/16`  | gitlab-qa-runners-2            | RESERVED
| `10.184.0.0`    | `10.191.255.255`   | `10.184.0.0/16`  | omnibus-build-runners          | RESERVED
| `10.185.2.0`    | `10.185.2.255`     | `10.185.2.0/24`  | gitlab-subscriptions-staging   | Stgsub GCP
| `10.185.3.0`    | `10.185.3.255`     | `10.185.3.0/24`  | gitlab-subscriptions-staging   | Stgsub GCP
| `10.185.4.0`    | `10.185.4.255`     | `10.185.4.0/24`  | gitlab-subscriptions-staging   | Stgsub GKE
| `10.185.5.0`    | `10.185.5.255`     | `10.185.5.0/24`  | gitlab-subscriptions-staging   | Stgsub GKE Service
| `10.185.6.0`    | `10.185.6.255`     | `10.185.6.0/24`  | gitlab-subscriptions-prod      | Prdsub GCP
| `10.185.7.0`    | `10.185.7.255`     | `10.185.7.0/24`  | gitlab-subscriptions-prod      | Prdsub GCP
| `10.185.8.0`    | `10.185.8.255`     | `10.185.8.0/24`  | gitlab-subscriptions-prod      | Prdsub GKE
| `10.185.9.0`    | `10.185.9.255`     | `10.185.9.0/24`  | gitlab-subscriptions-prod      | Prdsub GKE Service
| `10.186.0.0`    | `10.186.255.255`   | `10.186.0.0/16`  | gitlab-subscriptions-staging   | Stgsub GKE Pods
| `10.187.0.0`    | `10.187.255.255`   | `10.187.0.0/16`  | gitlab-subscriptions-prod      | Prdsub GKE Pods
| `10.188.0.0`    | `10.188.255.255`   | `10.188.0.0/16`  | gitlab-runway-staging          | Runway Staging
| `10.189.0.0`    | `10.189.255.255`   | `10.189.0.0/16`  | gitlab-runway-production       | Runway Production
| `10.201.0.0`    | `10.201.0.255`     | `10.201.0.0/24`  | gitlab-production              | `ci-gateway` VPC, haproxy-ci VMs second NIC
| `10.201.1.0`    | `10.201.1.15`      | `10.201.1.0/28`  | gitlab-staging                 | `ci-gateway` VPC, Private Service Connect subnet `psc-ci-c`
| `10.201.2.0`    | `10.201.2.255`     | `10.201.2.0/24`  | gitlab-production              | `ci-gateway` VPC, GKE haproxy-ci node pool second interface (`gitlab-3okls`)
| `10.201.3.0`    | `10.201.3.255`     | `10.201.3.0/24`  | gitlab-production              | `ci-gateway` VPC, pods on that interface (secondary range `haproxy-pods`)
| `10.203.0.0`    | `10.203.0.255`     | `10.203.0.0/24`  | gitlab-staging                 | `ci-gateway` VPC, haproxy-ci VMs second NIC
| `10.203.1.0`    | `10.203.1.255`     | `10.203.1.0/24`  | gitlab-staging                 | `ci-gateway` VPC, GKE haproxy-ci node pool second interface (`gitlab-36dv2`)
| `10.203.2.0`    | `10.203.2.255`     | `10.203.2.0/24`  | gitlab-staging                 | `ci-gateway` VPC, pods on that interface (secondary range `haproxy-pods`)
| `10.208.0.0`    | `10.208.0.255`     | `10.208.0.0/24`  | gitlab-release                 | **Release GCP**
| `10.209.0.0`    | `10.209.0.255`     | `10.209.0.0/24`  | gitlab-dev                     | **Dev GCP**
| `10.216.0.0`    | `10.223.255.255`   | `10.216.0.0/13`  | gitlab-production              | **Production GCP**
| `10.251.0.0`    | `10.251.255.255`   | `10.251.0.0/16`  | gitlab-dr                      | **DR GCP**
| `10.224.0.0`    | `10.231.255.255`   | `10.224.0.0/13`  | gitlab-staging                 | **Staging GCP**
| `10.232.0.0`    | `10.239.255.255`   | `10.232.0.0/13`  | gitlab-pre                     | **PreProd GCP**
| `10.248.0.0`    | `10.248.255.255`   | `10.248.0.0/16`  | N/A                            | **PreProd GCP**
| `10.249.0.0`    | `10.249.255.255`   | `10.249.0.0/16`  | N/A                            | **PreProd GCP**
| `10.250.0.0`    | `10.250.255.255`   | `10.250.0.0/16`  | gitlab-ops                     | **Ops GCP**
| `10.252.0.0`    | `10.252.255.255`   | `10.252.0.0/16`  | gitlab-restore                 | **Restore GCP**
| `10.253.0.0`    | `10.253.255.255`   | `10.253.0.0/16`  | N/A                            | **Ops GCP US-Central1**
| `10.255.0.0`    | `10.255.255.255`   | `10.255.0.0/16`  | db-benchmarking                | **DB Benchmarking GCP**
