# Hosted Runners Debugging Guide

**Kubernetes-based managers:** the private shard's runner managers are pods,
not VMs. The SSH and knife steps below do not apply to them; see
[kubernetes-runner-managers.md](kubernetes-runner-managers.md) for the
equivalents. Everything about the ephemeral job VMs themselves applies to
both fleets.

Debugging a hosted runner involves two main steps:

1. Verifying a runner-manager's ability to spin up ephemeral VMs.
2. Ensuring the ephemeral VMs can connect to GitLab.com or the CI Gateway.

---

## Quick Overview

For a visual walkthrough, check out this video: [Hosted Runners Testing](https://youtu.be/vcTFFHOlDaA).

---

## Part 1: Testing Ephemeral VM Creation

The most challenging aspect of testing runner-managers is composing the `docker-machine` command with all the required custom options. These options vary by manager, so we've created handy scripts to automate this process.

### Using `generate-create-machine.sh`

This script is typically located in the `/tmp` folder of runner-manager VMs. It generates another script based on the configurations in the `/etc/gitlab-runner/config.toml` file of each runner-manager.

#### Steps to Run

```bash
$ sudo su
# cd /tmp
# export VM_MACHINE=test1
# ./generate-create-machine.sh
# less create-machine.sh  # Review the generated script
# ./create-machine.sh     # Run the script
```

#### Example Output of a Successful Run

```plaintext
tmp# ./create-machine.sh
Running pre-create checks...
(test1) Check that the project exists
(test1) Check if the instance already exists
Creating machine...
(test1) Generating SSH Key
(test1) Creating host...
(test1) Opening firewall ports
(test1) Creating instance
(test1) Waiting for Instance
(test1) Uploading SSH Key
Waiting for machine to be running, this may take a few minutes...
Detecting operating system of created instance...
Waiting for SSH to be available...
Detecting the provisioner...
Provisioning with cos...
Copying certs to the local machine directory...
Copying certs to the remote machine...
Setting Docker configuration on the remote daemon...
Checking connection to Docker...
Docker is up and running!

To connect your Docker Client to the Docker Engine running on this VM, run: docker-machine env test1
```

---

## Part 2: Testing Ephemeral VM Connectivity

Once the ephemeral VM is created successfully, you can verify its connectivity.

### Steps to Test Connectivity

```bash
# docker-machine ssh test1
cos@test1 ~ $ curl -IL https://us-east1-c.ci-gateway.int.gprd.gitlab.net:8989
cos@test1 ~ $ curl -IL https://gitlab.com
```

#### Expected Outcome

- A successful call will return a `200` status code.

- If any command times out, it may indicate a network misconfiguration.

---

## Part 3: Connecting to a running job

If there is a problem in an existing job that is still running, it is possible to connect to it directly. Note that this should only be done for our own workloads.

### Get the runner-manager

This is visible on the web page for the job logs. Either on the top right, or in the logs themselves.

It will look something like this:

```
Running with gitlab-runner 18.4.0~pre.115.gb2218bab (b2218bab)
  on blue-4.saas-linux-small-amd64.runners-manager.gitlab.com/default J2nyww-sK, system ID: s_cf1798852952
```

This needs to be translated into the actual hostname, which in this case would be:

```
runners-manager-saas-linux-small-amd64-blue-4.c.gitlab-ci-155816.internal
```

This mapping is implicit, but can be discovered via:

```
host="$(cd ~/code/chef-repo && knife node list | grep -vE '^INFO:' | fzf -0 -1 | awk -F: '{print $1}')"
if [[ -n $host && "$hostname" != *".internal" ]]
then
  host="$(cd ~/code/chef-repo && knife node show "$host" | grep -vE '^INFO:' | yq '.FQDN')"
fi
```

Or via:

```
knife search 'roles:runners-manager' --attribute 'fqdn' --attribute 'cookbook-gitlab-runner.runners.default.global.name' --format json | grep -vE '^INFO:' | jq -r '.rows[].[]|[.fqdn, ."cookbook-gitlab-runner.runners.default.global.name"]|@tsv' | sort -n
```

### Get runner (job VM) and container

This is also in the job logs and looks like this:

```
Running on runner-j2nyww-sk-project-75050198-concurrent-0 via runner-j2nyww-sk-s-l-s-amd64-1759673243-5f16ceff...
```

The second part is the job VM, the first part is the container name on that job VM.

### SSH into the job

Now we have all the pieces to get a shell inside of the job.

First, SSH into the runner-manager:

```
ssh runners-manager-saas-linux-small-amd64-blue-4.c.gitlab-ci-155816.internal
```

Next up, SSH into the job VM. We do this through `docker-machine`.

```
iwiedler@runners-manager-saas-linux-small-amd64-blue-4.c.gitlab-ci-155816.internal:~# sudo -H docker-machine ssh runner-j2nyww-sk-s-l-s-amd64-1759673243-5f16ceff
```

This is a containerd-based container-optimized OS. It is possible to run a toolbox:

```
cos@runner-j2nyww-sk-s-l-s-amd64-1759673243-5f16ceff ~ $ toolbox
```

As well as docker commands. We can now get a shell inside of the job container:

```
cos@runner-j2nyww-sk-s-l-s-amd64-1759673243-5f16ceff ~ $ docker exec -it runner-j2nyww-sk-project-75050198-concurrent-0-d0c939fb2a356dee-predefined bash
```

---

## Debugging Step-Based Jobs (GitLab Functions)

Jobs that use [GitLab Functions](https://docs.gitlab.com/ci/yaml/#steps) execute through a step-runner gRPC service inside the build container, using a bootstrap → serve → proxy pattern. This section covers how to debug issues specific to step-based execution.

For a general overview of step-based execution and common errors, see the [Troubleshooting Guide](../troubleshooting-guide.md#troubleshooting-step-based-execution-gitlab-functions).

### Enable Debug Logging

For verbose step-runner output in the job log, set the `CI_FUNCS_LOG_LEVEL` CI/CD variable to `debug` on the job or project:

```yaml
variables:
  CI_FUNCS_LOG_LEVEL: debug
```

### Verify Bootstrap

The bootstrap stage copies the `gitlab-runner-helper` binary into the build container's shared volume.

1. Check for the `docker_bootstrap` stage in the job logs. A successful bootstrap will show the bootstrap container being created and exiting with code 0.

2. If you have access to the job VM, verify the binary exists in the container:

    ```bash
    docker exec <build_container> ls -la /opt/gitlab-runner/gitlab-runner-helper
    ```

    The binary should exist and be executable (`-rwxr-xr-x`).

3. Verify the bootstrap volume is mounted:

    ```bash
    docker inspect <build_container> --format '{{json .Mounts}}' | python3 -m json.tool | grep -A5 "/opt/gitlab-runner"
    ```

### Inspect Serve Process

In step-based jobs, the build container's main process is the helper binary running in serve mode.

1. Check the container's main process:

    ```bash
    docker exec <build_container> ps aux
    ```

    You should see a process like:

    ```
    /opt/gitlab-runner/gitlab-runner-helper steps serve bash
    ```

    If instead you see just `bash` or `sh` as PID 1, the job is using traditional execution, not steps.

2. Confirm the step-runner started successfully by checking for the **"step-runner is ready."** message in the job log. If this message is absent, the serve process did not initialize.

3. Check the container's command configuration:

    ```bash
    docker inspect <build_container> --format '{{json .Config.Cmd}}'
    ```

    For step-based jobs, this will include `steps serve` in the command chain.

### Container Inspection

Inspect step-related volumes and mounts on the job VM:

```bash
# List all volumes for the build container
docker inspect <build_container> --format '{{json .Mounts}}' | python3 -m json.tool

# Check for the /opt/gitlab-runner volume specifically
docker inspect <build_container> --format '{{range .Mounts}}{{if eq .Destination "/opt/gitlab-runner"}}Type={{.Type}} Source={{.Source}} RW={{.RW}}{{end}}{{end}}'
```

The `/opt/gitlab-runner` volume should be present and writable.

### Log Patterns

Step-based execution produces different log patterns compared to traditional execution:

**Step-based execution**:

- A `docker_bootstrap` stage appears before the build starts (`ExecutorStageBootstrap` internally).
- The bootstrap container is created and started with the command `gitlab-runner-helper steps bootstrap /opt/gitlab-runner/gitlab-runner-helper`.
- The build container command is prefixed with `/opt/gitlab-runner/gitlab-runner-helper steps serve`.
- Once the gRPC service is ready, the job log prints **"step-runner is ready."**.

**Traditional execution**:

- No bootstrap stage.
- No `/opt/gitlab-runner` volume creation.
- The build container runs the shell command directly (e.g., `bash`, `sh`).

### Unix Socket Verification

The step-runner gRPC service communicates over a Unix socket inside the build container. On Linux, the default path is `/tmp/step-runner.sock`.

1. Verify the socket exists:

    ```bash
    docker exec <build_container> ls -la /tmp/step-runner.sock
    ```

    The socket should be present as a socket file (type `s`).

2. If the socket does not exist, the serve process likely failed to start or has crashed. Check the container logs:

    ```bash
    docker logs <build_container>
    ```

3. Verify the serve process is still running (see [Inspect Serve Process](#inspect-serve-process) above). If the serve process has exited, the socket will no longer accept connections, and the proxy will fail to communicate with the step-runner.

---

## Troubleshooting Tips

### Common Issue: Network Misconfiguration

One frequent issue is a missing network configuration for the CI Gateway. Ensure that the network is allowed in the [CI Gateway configuration](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/7a5022fafbcd268e34b3f08b4d86aea8699db328/environments/gprd/variables.tf#L224).

If problems persist, verify the VM’s network settings and access permissions.
