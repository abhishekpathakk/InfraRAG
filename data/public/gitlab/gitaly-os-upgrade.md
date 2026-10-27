# Upgrading the OS of Gitaly VMs

Since most of our Gitaly VMs in staging and production are not part of a
replicated Gitaly cluster and are thus Single Points Of Failure, we've
established a process to perform upgrades that require downtime (e.g. Ubuntu
distribution upgrades, offline Kernel upgrades). This process builds a GCP VM
image using Packer, pre-baked with the omnibus-gitlab package version curently
deployed in the target environment.

## Upgrade playbooks

We created a set of Ansible playbooks to automate most of the process. They can
be found at
<https://gitlab.com/gitlab-com/gl-infra/ansible-workloads/gitaly-os-upgrade>.
Setup instructions are provided in the project's README.md

### Inventory

Currently the hosts inventory used by the playbooks is static. There exist
separate inventories for
[gstg](https://gitlab.com/gitlab-com/gl-infra/ansible-workloads/gitaly-os-upgrade/-/blob/master/inventory/gstg/all.yml)
and
[gprd](https://gitlab.com/gitlab-com/gl-infra/ansible-workloads/gitaly-os-upgrade/-/blob/master/inventory/gprd/all.yml).
The inventory files also determine the "batches" that are used to split the
execution of the playbooks between groups of hosts.

NOTE: For the steps that involve downtime [at most 10 hosts at a time are
processed
concurrently](https://gitlab.com/gitlab-com/gl-infra/ansible-workloads/gitaly-os-upgrade/-/blob/master/run.yml)
regardless of batch size.

### Executing the playbooks

The playbooks are setup to have a single point of entry that executes the whole
procedure in a mostly* idempotent manner. To run the playbooks, we employ a
wrapper that can be invoked as follows from the `gitaly-os-upgrade` repository
root:

```sh
bin/rebuild <environment> <batch>
```

For example:

```sh
bin/rebuild gprd 7
```

executes the playbooks on the production environment for the batch called
`batch7` in the `gprd` inventory.

*Note on idempotence: every execution of the playbooks creates a backup GCP disk
image for the hosts that are being targetted.

### Dry run

You can verify that Ansible can connect to the hosts and that the playbook steps
seem correct for execution by invoking the wrapper with the `--check` argument.
For example:

```sh
bin/rebuild gprd 7 --check
```

## Planning an upgrade

- Update the base packer image to match your expected OS base version
  <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/packer/gitaly.pkr.hcl#L3>
- Update the inventories for the target environments in the `gitaly-os-upgrade`
  project. It is recommended that your first batches are small and contain a
  representative sample of different types of nodes, to detect possible failures
  related to particularities of each node type in a more limited scope. For more
  discussion regarding host distribution in batches see
  <https://gitlab.com/gitlab-com/gl-infra/ansible-workloads/gitaly-os-upgrade/-/merge_requests/3>.
- Run the entire process in `gstg` before moving to `gprd`. The playbooks will
  perform pre and post upgrade validations for each execution.
- Coordinate execution times with release managers. You should make sure there's
  no deployments in progress while executing the change, to ensure the
  omnibus-gitlab version used to build the Packer image matches the one deployed
  in the environment

### Lessons learnt from previous upgrades

In April 2022 we performed an upgrade which is described
in [this epic](https://gitlab.com/groups/gitlab-com/gl-infra/-/epics/601).

We learnt that:

- we did not have to be as worried as we were for asking for longer maintenance windows
- the windows we asked for (4x of 2 hours each) were too short and we should have asked for 5x 4 hour windows
- it was helpful to have several people on the upgrade call with specific responsibilities
  which were: 1) IM, 2) Change technician, 3) SRE support, 4) Progress monitoring
- keeping Praefect servers separate made it easier to reason about specific failures

## Gotchas

- Prometheus re-generates its inventory from chef on a 30 minute cadence. If a
  gitaly host is being rebuilt at that moment, it will drop out of monitoring
  and stop getting scraped for 30 minutes. Thus, it is recommended to disable
  chef-client on prometheus-{01,02}-inf-gprd.c.gitlab-production.internal during
  the upgrade procedure.
- Fluentd's position file is stored on the root disk. Since the root disk is
  deleted during a rebuild, this will make fluentd replay all of its logs after
  the machine comes up for the first time. See
  <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/15621> for more
  details
- Because fluentd is configured with the packer VM hostname upon boot, initial
  logs (including the replayed ones) will have the wrong hostname. Only once
  chef runs and fixes up the hostname in fluentd config do we get the correct
  one. Possible fix: Disable fluentd during image building. This will delay log
  ingestion until chef runs, but will avoid the broken hostname.
