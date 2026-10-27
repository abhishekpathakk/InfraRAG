# Linux CI/CD Runners fleet graceful shutdown procedure

## Preflight checklist

Before you will start any work

1. [ ] Make sure that you meet [Administrator prerequisites](README.md#administrator-prerequisites) before you will
   start any work.
1. [ ] [Not in a PCL time window](../README.md#production-change-lock-pcl).
1. [ ] [Change Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/) issue was
   created for the change that requires the usage of Graceful Shutdown.

## What is Graceful Shutdown

However jobs are physically executed in different environments depending on the configured executors, the full data
about the job, it's current status, buffer of the log, details about connection to the execution environment etc.
are stored in GitLab Runner process' memory.

Simple termination of a Runner that is currently handling a running job have very negative consequences:

1. From GitLab's (so also user's!) perspective the job looks like cancelled. As such cancel is not asked nor expected
   by the user, it's perceived as a system failure and in a bigger scale will be reported as a platform outage.

1. Despite the job log is anymore updated nor the status is passed, the job execution keeps happening because nothing
   have requested it termination. This may also have negative consequences, depending on what the job was doing.

As each of our Runner Managers is handling even up to ~800 jobs at once, terminating the process with - for example -
`kill -9 PID_OF_RUNNER` means that these 800 jobs will be left unhandled and look like unwillingly canceled from the
GitLab user perspective.

For that purpose GitLab Runner have built in procedure that we name `Graceful Shutdown`.

When Graceful Shutdown is initiated, Runner process stops asking for new jobs but continues to execute the ones that
were already started. Only when the last job is finished and the job status is updated on GitLab side, the process
exits.

Now, because jobs can hang, we need to be able to force the shutdown.

In case of our CI Runners fleet, the Runners are installed as `systemd` services. The service definition is overridden
to use the `SIGQUIT` signal to initiate Graceful Shutdown. The service is also configured to force-terminate the process
after 7200 seconds, which should be enough for most of the legitimate jobs to exit.

To handle Runner termination, configuration changes and new version deployments we have dedicated scripting
that orchestrates all required commands.

### Graceful Shutdown and different Runner Manager types (srm, gsrm, prm, gdsrm etc.)

As [it's described](../README.md#runner-types), we maintain different types of Runner Managers. All managers
from within one group share the same execution environment setting, capacity etc. As running  Graceful Shutdown
means that a Runner doesn't request new jobs, it's important to remember that we can shutdown only one runner from
within a group at once.

For example, let's consider we have two `shared-runners-manager-X` (`srm1` and `srm2`) and two
`private-runners-manager-X` (`prm1` and `prm2`). When shutting down Runner processes for whatever reason, we can
terminate for example both `srm1` and `prm1` at once. Or `srm1` and `prm2`. But we can't never terminate both `srm1`
and `srm2` or both `prm1` and `prm2`. Only one `srmX` and only one `prmX` can be down (or in the process of going
down with the Graceful Shutdown) at once.

## Graceful Shutdown scripting

We have a script at `/root/runner_upgrade.sh` that abstracts all the steps needed for Graceful Shutdown handling.
The script is added from the
[`cookbook-wrapper-gitlab-runner` cookbook](https://gitlab.com/gitlab-cookbooks/cookbook-wrapper-gitlab-runner/-/blob/master/files/default/runner_upgrade.sh).

Always use it instead of interacting directly with Systemd's Runner service or with the process itself (for example
don't use the `kill` command!).

## Graceful Shutdown procedures

All commands that are described bellow can be executed either directly on the host (after SSH-ing there) or through
`knife ssh`. by specifying a node selector or a role selector.

With node selector remember to match only one node of a specific type at once.

With role selector, always try to use the less general role. For example, instead of using `gitlab-runner-base`,
use `gitlab-runner-srm` or `gitlab-runner-prm` role. Also always use the `-C 1` flag to instruct `knife ssh` to
run the command on only one runner at a time.

### How to stop Runner Manager with Graceful Shutdown

1. Run the stop script:

    ```shell
    sudo /root/runner_upgrade.sh stop
    ```

    This command will suspend `chef-client` (to make sure it will not restart Runner's service automatically nor add
    any other unexpected change) and terminate Runner's process with the usage of Graceful Shutdown.

1. Do whatever you needed to do with terminated Runner.

1. Restart the Runner with:

    ```shell
    sudo /root/runner_upgrade.sh update
    ```

    This will restore the `chef-client`, cleanup old non-removed Docker Machine VMs that were left, refresh the
    configuration and finally start the Runner process.

### How to stop or restart Runner Manager's VM with Graceful Shutdown

1. Do shutdown

    1. If you want to stop the VM

        1. Run the script:

            ```shell
            sudo /root/runner_upgrade.sh stop_and_poweroff
            ```

            This command will suspend `chef-client` (to make sure it will not restart Runner's service automatically nor add
            any other unexpected change) and terminate Runner's process with the usage of Graceful Shutdown. Finally it
            will turn off the VM.

        1. Do whatever you needed to do with Runner's VM terminated.

        1. Restart the VM in GCP console.

    1. If you want to restart the VM, run the script:

        ```shell
        sudo /root/runner_upgrade.sh stop_and_reboot
        ```

        This command will suspend `chef-client` (to make sure it will not restart Runner's service automatically nor add
        any other unexpected change) and terminate Runner's process with the usage of Graceful Shutdown. Finally it
        will reboot the VM.

1. Restart the Runner with:

    ```shell
    sudo /root/runner_upgrade.sh update
    ```

    This will restore the `chef-client`, cleanup old non-removed Docker Machine VMs that were left, refresh the
    configuration and finally start the Runner process.

### How to proceed Runner Manager configuration changes with Graceful Shutdown

If your [configuration change](configuration.md) requires a shutdown of the Runner, it's easiest to follow
the [deployment procedure](../macos/deployment.md).
