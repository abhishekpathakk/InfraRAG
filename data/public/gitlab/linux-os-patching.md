# Linux OS Patching

This document is intended to overview system patching practices at GitLab, and provide guidance for ensuring systems stay up to date with the latest security fixes for individual systems.

## Scope

This document targets VM instances running Linux based operating systems that make up the numerous fleets that directly support GitLab.com. There may be unique Linux deployments, or one-off systems where additional consideration may be required, and it should be expected that the scope of this document will change over time as the service and it's deployment evolve.

### Goals

- Identify and classify critical systems where patching is required.
- Establish a patching cadence for systems as they exist today, determined by the system's risk exposure.
- Outline system owners and contacts who should be responsible for the patching of individual systems.
- Provide an overview of the existing patching processes, and prerequisites for doing so.

### System definitions

- Internet facing Linux OS
  - These systems are exposed directly to the internet and have a larger attack surface because of this.
  - Examples:
    - bastion hosts
    - HAProxy
- Internal Linux OS
  - Linux systems that are not directly accessible from external networks, and malicious access would need to traverse other secure systems first.
  - Examples:
    - Gitaly
    - Patroni
    - Redis

## Linux Patching Overview

### Distribution Updates

GitLab almost exclusively deploys Ubuntu as the base operating system for VMs supporting GitLab.com. By default, Canonical provides 5 years of security patching for their LTS releases (releases on even numbered years in April).

All of our Ubuntu systems have unattended upgrades enabled, meaning they will automatically install *security* patches on a daily basis.

While there is currently no guaranteed support for packages outside of the Ubuntu `main` repositories, we should strive to keep our fleet within the official 5 year LTS support window, as packages in additional repositories such as `universe` and `multiverse` tend to no longer receive updates past this period.

### Ubuntu Pro

#### ESM (INFRA-ONLY)

For machines that we enroll in Ubuntu Pro, ESM (extended security maintenance) coverage extends security patching support for packages in the `main` Ubuntu repository out to 10 years. This support does not extend to packages installed via the `universe` or `multiverse` repositories, or PPA respositories maintained by parties other than Canonical. Canonical offers support for the packages in the `universe` repository for an additional licensing fee that we may consider in the future.

#### Kernel Livepatch

This service allows us to apply High and Critical severity security fixes to running machines without the need to reboot the instance. Each kernel supported by Livepatch has a limited [support period](https://ubuntu.com/security/livepatch/docs/livepatch/reference/kernels) ranging from 9-13 months, where they are eligible for updates before a reboot will be required to receive further updates. This means, at minimum, every machine should be restarted once a year to ensure critical kernel security fixes will be available.

#### Requirements

Any of the following scenarios will qualify a system for enrollment in Ubuntu Pro:

- The OS is no longer in it's LTS support window.
- The systems cannot be rebooted without downtime on GitLab.com
- There is no automation available for applying updates and rebooting the systems.

## Services

The major Linux fleets that support GitLab.com are:

| Service | Owner | Exposure | Maintenance Impact | Automation | Ubuntu Pro |Cadence (weeks) |
| ------- | ----- | -------- | :----------------: | :--------: | ---------- |--------------- |
| [GKE](systems/gke.md)     | runway | external | low | partial | N/A | external |
| [Runner Managers](systems/runner-managers.md) | scalability:practices | internal | low | partial| no | 8 |
| [HAProxy](systems/haproxy.md) | networking_and_incident_management | external | low | partial | no | 8 |
| [Gitaly](systems/gitaly.md) | tenant_services | internal | high | no | yes | as needed |
| [Patroni](systems/patroni.md) | reliability_database_reliability | internal | low | no | yes | 8 |
| [PGBouncer](systems/pgbouncer.md) | reliability_database_reliability | internal | low | no | yes | 8 |
| [Redis](systems/redis.md) | data-access::durability | internal | low | no | yes | 8 |
| [Console](systems/console.md) | none | internal | low | no | yes | 8 |
| [Deploy](systems/deploy.md) | none | internal | medium | no | yes | 12 |
| [Bastions](systems/bastions.md) | none | external | low | partial | no | 8 |

### Definitions

#### Maintenance Impact

- Low:
  - The service is deployed in a highly available capacity and individual instances can be taken offline with no impact to service usability.
  - The service is not highly available, but brief outages do not impact any other systems or processes.
- Medium:
  - The service is deployed in a highly available capacity, but there may be system degradation as a result of taking instances offline for maintenance.
  - The service is not deployed in a highly available capacity, and coordination may be required to prevent internal process disruption. Customers are not impacted.
- High:
  - The service is not deployed in a highly available capacity, downtime of portions of GitLab.com is required to facilitate patching activities.

#### Automation

- no
  - No automation exists. Maintenance activities are initiated and executed by an SRE for each component in the system.
- partial
  - Either maintenance initiation, or execution is required to be done by hand, but the other is handled by an automated system.
- yes
  - Initiation, and execution of maintenance is handled by automated systems. No SRE involvement is required to keep systems up to date

#### Cadence

The patching cadence for systems will be influenced by our established [SLAs](https://handbook.gitlab.com/handbook/security/product-security/vulnerability-management/sla/) for vulnerability management, weighted by the system's maintenance impact and whether automation exists for performing maintenance on the system. The goal is to have all systems have a low impact while under maintenance, that is fully automated.

General guidance for patching cadence will look like:

| Impact | Automation | Cadence |
| ------ | ---------- | ------- |
| low    | yes        | 4 weeks |
| low    | no         | 8 weeks |
| medium | yes        | 4 weeks |
| medium | no         | 12 weeks |
| high   | no         | as needed* |
| high   | yes        | as needed* |

_*As needed means that patching and reboots will be done to maintain security compliance by following guidance for "Unscheduled Patching"_

Systems where the patch management lifecycle is controlled by a 3rd party may be designated as "external"

## Unscheduled Patching

It may be necessary to perform patching outside of a system's normal cadence to respond to new threats that are discovered and are actively being exploited. In these circumstances we will look to the SLAs defined for the relevant vulnerability CVE score, and initiate patching processes as appropriate to maintain compliance and security of the systems.

### Priorities

A simplistic order of operations that can be followed to patches are applied first to systems that have the most risk exposure can be (refer to system definitions above):

1. Ensure all systems are under active support, and are not EoL.
1. Externally accessible systems are up to date
1. Internally accessible systems are up to date

When targeting systems to update, the first goal should be to ensure that all systems are whithin their designated support window. This is to ensure that if security vulnerabilities are found, these systems will have a path towards resolution, even if only passively.

We make no distinction between non-production and production systems intentionally, as patch application should always first be applied to non-production systems before production, with the priority set by the risk exposure of the production system.
