# Linux CI/CD Runners fleet configuration changes

## Preflight checklist

Before you will start any work

1. [ ] Make sure that you meet [Administrator prerequisites](README.md#administrator-prerequisites) before you will
   start any work.
1. [ ] [Not in a PCL time window](../README.md#production-change-lock-pcl).
1. [ ] [Change Management](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/) issue was
   created for this configuration change.

## What is the configuration change in CI Runners fleet case

Configuration change is any change related to Runner's configuration that is not
a [different version of GitLab Runner Deployment](../macos/deployment.md). However, some configuration changes require
full Runner restart, which... is easiest to do by following the deployment procedure. I know - it's complicated.

## When configuration change applying requires Runner restart

> **Notice:** Remember that any time when Runner or Runner's host needs to be restarted, the
> [Graceful Shutdown](graceful-shutdown.md) procedure must be used!

Most of settings configurable in `config.toml` can be updated without a need to restart the Runner. Therefore
you can follow the simple path.

The settings that require Runner's restart, are:

- configuration of the internal metrics exporter, as the exporter is started once at the beginning of the process
  (the [`listen_address`](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-global-section)
  setting),
- configuration of the CI Web Session Terminal, for the same very reason (the
  [`[session_server]`](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-session_server-section)
  section).

For a reference - all `config.toml` settings are documented at: <https://docs.gitlab.com/runner/configuration/advanced-configuration/>.

Apart of that Runner should automatically reload the updated configuration file within a minute since the file
update and should apply all other settings.

### Re-usable Docker Machine settings specific case

On some of our Runner Managers - `private-runners-manager-X` and `gitlab-shared-runners-manager-X` to be precise -
the Docker Machine executor is configured to re-use an existing autoscaled VM for several subsequent jobs.

This means that if we will change
[any settings of the autoscaled VMs](https://docs.gitlab.com/runner/configuration/advanced-configuration/#the-runnersmachine-section)
(for simplification read: anything that's in the `[runners.machine] => MachineOptions` setting), it will be immediately
applied to newly created created VMs but will have no effect on the exiting ones. This includes both machines that
are currently in use **and** idle machines that were already created. Usually it takes up to 24 hours for
all of the "old" VMs to be recycled and replaced by a new ones that are using a "new" configuration.

If you want or need to apply the changed VM settings immediately, then apply the changes by following the
[deployment procedure](../macos/deployment.md). This will enforce Runner to finish all jobs, go down, **cleanup all existing
autoscaled VMs**, start up and create new VMs **with the new configuration** accordingly to the autoscaling settings.

## Configuration changes procedures

### Configuration change requiring Runner restart

Just follow the [deployment procedure](../macos/deployment.md). Just skip the part of updating version information in the
chef role, as in this case it's not what you want to change.

However, if additionally you need the Runner Manager's VM to be stopped or rebooted, then follow the
[Runner Manager VM restart procedure](graceful-shutdown.md#how-to-stop-or-restart-runner-managers-vm-with-graceful-shutdown).

### Configuration change that doesn't require Runner restart

1. **Update chef role (or roles)**

    In `chef-repo` directory execute:

    ```shell
    $EDITOR roles/gitlab-runner-prm.json
    ```

    where `gitlab-runner-prm` is a role used by nodes that you are updating. Please check the
    [roles to runners mapping section](README.md#roles-dependency) to find which role you're interested in.

1. Commit and push changes to the remote repository:

    ```shell
    git checkout master && \
        git pull && \
        git checkout -b origin update-prmx-configuration && \
        git add roles/gitlab-runner-prm.json && \
        git commit -m "Update prmX configuration" && \
        git push -u origin update-prmx-configuration
    ```

   After pushing the commit, create, review and work upon a merge of the MR. When the MR gets approved and merged,
   wait for the merge pipeline to finish and double check in the `production_dry_run` job, if the dry-run tries to
   upload only the role file updated above.

   If yes - hit `play` on the `apply_to_prod` job and wait until the job on Chef Server will be updated.

1. Wait for `chef-client` to automatically update the configuration. All our hosts managed by Chef are configured
   to run `chef-client` automatically in 30 minutes intervals. If you can't wait for that to happen, just login
   to the machine where you want to apply the changes and run:

    ```shell
    sudo chef-client
    ```

1. If your changes were related to `config.toml` configuration file of GitLab Runner, you can confirm that
   an updated version was reloaded by the Runner, by using the following command:

    ```shell
    knife ssh -C1 -afqdn 'roles:gitlab-runner-prm' -- 'sudo -i journalctl -u gitlab-runner | grep "Configuration loaded"'
    ```
