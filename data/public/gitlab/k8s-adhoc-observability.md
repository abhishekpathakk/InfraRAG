# Ad hoc observability tools on Kubernetes nodes

Recipes for capturing and analysing ad hoc observability data (resource usage, performance) on a GKE node.

Some tools are not container-aware and have unintuitive scoping. Gotchas are called out per section.

> [!note]
> GKE COS nodes use `containerd`; container operations use `crictl`, not `docker`.
> cgroup v2 is the default from GKE 1.33. cgroup v1 was deprecated in Kubernetes 1.31 and removed in 1.35 — see [Migrate to cgroupv2](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/migrate-cgroupv2). Some examples below still show cgroup v1 paths; on a v2 node the paths follow `/sys/fs/cgroup/kubepods.slice/.../cpu.max` instead.

## Helper scripts overview

Some helper scripts to facilitate ad hoc observations and exploratory work are available in this repo's `scripts/gke` directory.

When running these scripts you must explicitly run `bash <script>`, because our home directories on the GKE nodes are subject to
the `noexec` mount option.  To run shell scripts we must explicitly invoke the shell binary (in this case `/bin/bash`).

The sections below cover more details, but as a brief summary:

```
Get the helper scripts:

$ git clone https://gitlab.com/gitlab-com/runbooks.git
$ cd runbooks/scripts/gke/

CPU profiling:

$ bash perf_flamegraph_for_all_running_processes.sh
$ bash perf_flamegraph_for_container_id.sh [container_id]
$ bash perf_flamegraph_for_container_of_pid.sh [pid]
$ bash perf_flamegraph_for_pod_id.sh [pod_id]

Mapping between IDs for PIDs, pods, containers, and cgroups:

$ bash container_id_for_pid.sh [pid]
$ bash container_id_for_cgroup.sh [cgroup_path]

$ bash pod_id_for_pid.sh [pid]
$ bash pod_id_for_cgroup.sh [cgroup_path]

$ bash cgroup_for_container_id.sh [container_id]
$ bash cgroup_for_pid.sh [pid]
$ bash cgroup_for_pod_id.sh [pod_id]

Packet captures:

$ bash tcpdump_on_gke_node.sh [max_duration] [tcpdump_options...]
$ bash tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh [pod_id] [max_duration_seconds] [tcpdump_options...]
$ bash tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh [pod_id] [max_duration_seconds] [tcpdump_options...]

$ bash ip_addr_for_pod_id.sh [pod_id]
```

## Picking a GKE node

All of these tools and methods are meant to be run on a specific GKE node.

If you have not already chosen a target GKE node to observe, here are some ways to list the currently running nodes.

List GKE nodes:

```
➜  ~ gcloud --project gitlab-pre compute instances list --filter 'name:gke-pre-gitlab-gke-redis'
NAME                                                 ZONE        MACHINE_TYPE   PREEMPTIBLE  INTERNAL_IP   EXTERNAL_IP  STATUS
gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc  us-east1-b  c2-standard-8               10.232.20.65               RUNNING
gke-pre-gitlab-gke-redis-ratelimiting-b9fd9cef-42t5  us-east1-c  c2-standard-8               10.232.20.41               RUNNING
gke-pre-gitlab-gke-redis-ratelimiting-3378c320-7uwa  us-east1-d  c2-standard-8               10.232.20.16               RUNNING
gke-pre-gitlab-gke-redis-ratelimiting-3378c320-h1j3  us-east1-d  c2-standard-8               10.232.20.67               RUNNING
```

or

```
$ kubectl get nodes | grep -e 'NAME' -e 'redis-ratelimiting' | head -n 3
NAME                                                  STATUS   ROLES    AGE     VERSION
gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-l90m   Ready    <none>   3d17h   v1.33.4-gke.100
gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh   Ready    <none>   3d17h   v1.33.4-gke.100
```

SSH into node:

```
➜  ~ gcloud --project gitlab-pre compute ssh gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc
```

## CPU profiling

Once you SSH onto a GKE node, you can capture a CPU profile for a container, a pod, or the whole host.

### Usage

All of the following helper scripts use the same approach and output format.
The main difference is letting you optionally scope the capture to a container or pod:

```
bash perf_flamegraph_for_all_running_processes.sh
bash perf_flamegraph_for_container_id.sh [container_id]
bash perf_flamegraph_for_container_of_pid.sh [pid]
bash perf_flamegraph_for_pod_id.sh [pod_id]
```

### Profiling the whole GKE node

Install and run `perf_flamegraph_for_all_running_processes.sh`:

```
igor@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ wget https://gitlab.com/gitlab-com/runbooks/-/raw/master/scripts/gke/perf_flamegraph_for_all_running_processes.sh

igor@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ bash perf_flamegraph_for_all_running_processes.sh

...

Starting capture for 60 seconds.
[ perf record: Woken up 33 times to write data ]
[ perf record: Captured and wrote 9.275 MB perf.data (47520 samples) ]
Please do not use --share-system anymore, use $SYSTEMD_NSPAWN_SHARE_* instead.
Spawning container igor-gcr.io_google-containers_toolbox-20201104-00 on /var/lib/toolbox/igor-gcr.io_google-containers_toolbox-20201104-00.
Press ^] three times within 1s to kill container.
Container igor-gcr.io_google-containers_toolbox-20201104-00 exited successfully.

Results:
Flamegraph:       /tmp/perf-record-results.6VUGMYa4/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc.20220331_144401_UTC.all_cpus.flamegraph.svg
Raw stack traces: /tmp/perf-record-results.6VUGMYa4/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc.20220331_144401_UTC.all_cpus.perf-script.txt.gz
```

Now you can scp the flamegraph to your local machine:

```
➜  ~ gcloud --project gitlab-pre compute scp gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc:/tmp/perf-record-results.6VUGMYa4/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc.20220331_144401_UTC.all_cpus.flamegraph.svg .
```

#### Profiling a specific container

Similar to the above, you can profile a single container rather than the whole host.

Find and ssh into a GKE node:

```
gcloud compute instances list --project gitlab-pre --filter 'name:gke-pre-gitlab-gke-redis'
gcloud compute ssh --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc
```

On the GKE node, fetch the helper script:

```
git clone https://gitlab.com/gitlab-com/runbooks.git
cd runbooks/scripts/gke/
```

Choose your target PID, and run the profiler on just its container:

```
TARGET_PID=$( pgrep -n -f 'redis-server .*:6379' )
bash ./perf_flamegraph_for_container_of_pid.sh $TARGET_PID
```

Alternately, you can specify the target container by id:

```
CONTAINER_ID=$( crictl ps --latest --quiet --name 'redis' )
bash ./perf_flamegraph_for_container_id.sh $CONTAINER_ID
```

On your laptop, download the flamegraph (and optionally the perf-script output for fine-grained analysis):

```
gcloud compute scp --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc:/tmp/perf-record-results.oI3YR698/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc.20220414_010939_UTC.container_of_pid_7154.flamegraph.svg .

gcloud compute scp --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc:/tmp/perf-record-results.oI3YR698/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc.20220414_010939_UTC.container_of_pid_7154.perf-script.txt.gz .
```

## Finding relationships between processes, containers, and pods

After SSHing to a GKE node, you can use `crictl` to view containers and pods running on that node.

To find which container or pod owns a process, you can use the utilities in the runbooks repo's `scripts/gke` directory,
as shown below.

This is all run from a normal shell on the GKE node (outside the target container, in the GKE node's root process namespace).

Choose a process to inspect.

> [!note]
> This is the process's PID from the host's root namespace, not its PID from within the container's namespace.

```
msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ TARGET_PID=$( pgrep -f 'redis-server.*:6379' )

msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ ps uwf $TARGET_PID
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
chronos+    7154  1.5  0.0 139808 10200 ?        Ssl  Mar15 720:01 redis-server *:6379
```

Find the process's container id, and use `crictl` to display the container's summary info:

```
msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ crictl ps --id $( bash container_id_for_pid.sh "$TARGET_PID" )
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID
89e7d6da5f404       be0431d8c1328       4 weeks ago         Running             redis               0                   bb2d2ec8e1499
```

Find the process's pod id, and use `crictl` to display all containers in that pod:

```
msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-mabc ~ $ crictl ps --pod $( bash pod_id_for_pid.sh "$TARGET_PID" )
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID
f70ffec5e32e7       2600417bb7548       4 weeks ago         Running             metrics             0                   bb2d2ec8e1499
ad8d09b753bd6       de6f7fadcaf3d       4 weeks ago         Running             sentinel            0                   bb2d2ec8e1499
89e7d6da5f404       be0431d8c1328       4 weeks ago         Running             redis               0                   bb2d2ec8e1499
```

## Quick reference: Explore pods, containers, and images using `crictl`

All GKE nodes have the `crictl` utility installed by default.

This tool queries the container runtime (in this case runc/containerd) to expose details of the running pods and containers.

The following quick reference covers some common uses:

```
# List containers.
$ crictl ps

# List the containers of a given pod id (short or long id format).
$ crictl ps --pod $POD_ID

# List pods.
$ crictl pods

# List pods in namespace "redis".
$ crictl pods --namespace redis

# List pods having a specific label.
$ crictl pods --label 'app.kubernetes.io/instance=redis-ratelimiting'

# Pick an example pod or container id for use in subsequent commands.
$ POD_ID=$( crictl pods --latest --quiet --namespace redis )
$ CONTAINER_ID=$( crictl ps --latest --quiet --name sentinel )

# Inspect the details of a pod, container, or image.  JSON by default.
$ crictl inspectp $POD_ID
$ crictl inspect $CONTAINER_ID
$ crictl inspecti $IMAGE_ID

# Execute a command in a container.
$ crictl exec -it $CONTAINER_ID ps -ef
$ crictl exec -it $CONTAINER_ID which redis-cli

# Review available subcommands and arguments.
$ crictl --help
$ crictl ps --help
```

## Packet captures on a GKE node

Capturing a small sample of network traffic can be diagnostically useful.

The following helper scripts facilitate this:

```
tcpdump_on_gke_node.sh [max_duration_seconds] [tcpdump_options]
tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh [pod_id] [max_duration_seconds] [tcpdump_options]
tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh [pod_id] [max_duration_seconds] [tcpdump_options]
```

GKE nodes do not have `tcpdump` installed by default.  These scripts install it via toolbox,
choose a network interface to capture, run `tcpdump` with whatever additional options you specify,
and write the resulting compressed capture file to `/var/pcap/`.  From there, you can download
the pcap file for analysis.

### Quick reference: Packet capture commands

All of the following commands are run on a GKE node, outside of any container.

```
# Fetch the tools.
$ git clone https://gitlab.com/gitlab-com/runbooks.git
$ cd runbooks/scripts/gke/

# Capture all traffic on the host for up to 30 seconds or 10K packets, whichever comes first.
$ bash ./tcpdump_on_gke_node.sh 30 -c 10000

# Capture 10 seconds of traffic on the host for port 6379, regardless of pod.
$ bash ./tcpdump_on_gke_node.sh 10 'port 6379'

# Choose a pod to capture.
$ crictl pods
$ POD_ID=$( crictl pods --latest --quiet --namespace redis )

# Show the pod IP address.
$ bash ./ip_addr_for_pod_id.sh $POD_ID

# Capture 10 seconds of traffic to a single pod.  Includes loopback traffic between local containers.
$ bash ./tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh "$POD_ID" 10

# Same as above, but excludes loopback traffic.
$ bash ./tcpdump_on_gke_node_for_pod_id.using_pod_iface.sh "$POD_ID" 10

# Capture 10 seconds of traffic to a single pod.
# Save space by capturing only incoming requests (not response data) on port 6379.
$ bash ./tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh "$POD_ID" 10 'dst port 6379'
```

### Gotchas

Before running large or long-running packet captures, be aware of the following gotchas:

* Disk space:
  * The pcap files are saved to `/var/pcap` on the GKE host.
  * This is a disk-backed filesystem, so writing there is safer than writing to a `tmpfs` filesystem (i.e. does not consume memory).
  * However, its space is limited.  The same single filesystem holds container images and logs.  So be frugal.
  * If you generate a large pcap file, delete it when done.
* Cannot Ctrl-C a running capture:
  * Because we must run `tcpdump` inside the `toolbox` container, we cannot interactively interrupt the capture by pressing Ctrl-C.
  * Choose a reasonable max duration when running the tcpdump wrapper scripts.  Optionally also specify a max packet count (`-c 10000`).
  * If you need to quickly kill a capture, start a new shell on the GKE node and kill the `tcpdump` process:

    ```
    sudo pkill tcpdump
    ```

### Clone the tools onto your target GKE node

Find and ssh into a GKE node:

```
gcloud --project gitlab-pre compute instances list --filter 'name:gke-pre-gitlab-gke-redis'
gcloud compute ssh --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh
```

On the GKE node, fetch the helper script:

```
git clone https://gitlab.com/gitlab-com/runbooks.git
cd runbooks/scripts/gke/
```

### Capturing traffic at the host or pod level

> [!caution]
> Treat packet captures as potentially sensitive data.

Typically each pod runs in its own network namespace.
Multiple pods may have processes listening on the same port.

To capture traffic on that port for all pods, capture at the host level.
The following example captures for 10 seconds all traffic on port 6379
in both directions for all pods.

```
bash ./tcpdump_on_gke_node.sh 10 'port 6379'
```

To do the same capture for a specific single pod, choose a pod id, and run:

```
POD_ID=$( crictl pods --latest --quiet --namespace redis )
bash ./tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh "$POD_ID" 10 'port 6379'
```

For reference during analysis, it is often helpful to know the pod's IP address:

```
$ bash ./ip_addr_for_pod_id.sh $POD_ID
10.235.8.8
```

When the capture finishes, it will show the full path to the output pcap file.

On your laptop, download the file using `gcloud compute scp`:

```
$ gcloud compute scp --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh:/var/pcap/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz  /tmp/
No zone specified. Using zone [us-east1-b] for instance: [gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh].
External IP address was not found; defaulting to using IAP tunneling.
gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa79 100%   23KB 152.1KB/s   00:00
```

### Demo

#### Capture

Choose a GKE host that is running a pod we want to observe.
Here we use `kubectl get pods` to find a node that is currently running a redis pod.

```
msmiley@saoirse:~$ kubectl get pods -n redis -o wide | grep 'redis'
redis-ratelimiting-node-0   4/4     Running   2          30h   10.235.8.8   gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh   <none>           <none>
```

SSH to the GKE node.

```
msmiley@saoirse:~$ gcloud compute ssh --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh
```

Choose a pod.

```
msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh ~/runbooks/scripts/gke $ POD_ID=$( crictl pods --latest --quiet --namespace redis )

msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh ~/runbooks/scripts/gke $ echo $POD_ID
7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6

msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh ~/runbooks/scripts/gke $ crictl ps --pod $POD_ID
CONTAINER           IMAGE               CREATED             STATE               NAME                ATTEMPT             POD ID
f090b746ef29c       9319ef6fd72b0       31 hours ago        Running             sentinel            2                   7373dfce7087b
35c62fcef2873       6847317f2c777       31 hours ago        Running             process-exporter    0                   7373dfce7087b
f2927ce7eafd3       a9ef660d48b40       31 hours ago        Running             metrics             0                   7373dfce7087b
8ad5f5213991b       c7504ce63cbcb       31 hours ago        Running             redis               0                   7373dfce7087b
```

Run the capture.

```
msmiley@gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh ~/runbooks/scripts/gke $ bash ./tcpdump_on_gke_node_for_pod_id.using_pod_netns.sh "$POD_ID" 10 'port 6379'
Setting up toolbox.  (May take up to a minute during first run.)
tcpdump is already the newest version (4.9.3-1~deb10u1).
0 upgraded, 0 newly installed, 0 to remove and 1 not upgraded.
jq is already the newest version (1.5+dfsg-2+b1).
0 upgraded, 0 newly installed, 0 to remove and 1 not upgraded.

Capturing to pcap file: gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap
Please do not use --share-system anymore, use $SYSTEMD_NSPAWN_SHARE_* instead.
Spawning container msmiley-gcr.io_google-containers_toolbox-20201104-00 on /var/lib/toolbox/msmiley-gcr.io_google-containers_toolbox-20201104-00.
Press ^] three times within 1s to kill container.
tcpdump: listening on any, link-type LINUX_SLL (Linux cooked), capture size 262144 bytes
644 packets captured
847 packets received by filter
0 packets dropped by kernel
Container msmiley-gcr.io_google-containers_toolbox-20201104-00 exited successfully.
Compressing pcap file.
/media/root/var/pcap/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap:  81.5% -- replaced with /media/root/var/pcap/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz
Results:
-rw-r--r-- 1 root root 23K May 20 22:45 /var/pcap/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz
```

Download the pcap file for analysis.

```
msmiley@saoirse:~$ gcloud compute scp --project gitlab-pre gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh:/var/pcap/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz  /tmp/
No zone specified. Using zone [us-east1-b] for instance: [gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh].
External IP address was not found; defaulting to using IAP tunneling.
gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa79 100%   23KB 152.1KB/s   00:00
```

#### Analysis

Analyze the pcap as you normally would.  Example:

```
$ PCAP_FILE=/tmp/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz

$ export TZ=UTC

$ capinfos -aceuxs $PCAP_FILE
File name:           /tmp/gke-pre-gitlab-gke-redis-ratelimiting-231e75c5-rpfh.pod_7373dfce7087b83d7d9040dd3149a3a81ff14c946f572aa7949a39a694eb69b6.20220520_224447.pcap.gz
Number of packets:   644
File size:           23 kB
Capture duration:    8.550298 seconds
First packet time:   2022-05-20 22:44:50.497803
Last packet time:    2022-05-20 22:44:59.048101
Average packet rate: 75 packets/s

$ tshark -r $PCAP_FILE -q -z conv,ip
================================================================================
IPv4 Conversations
Filter:<No Filter>
                                               |       <-      | |       ->      | |     Total     |    Relative    |   Duration   |
                                               | Frames  Bytes | | Frames  Bytes | | Frames  Bytes |      Start     |              |
10.232.4.103         <-> 10.235.8.8               105 19 kB         105 21 kB         210 40 kB         0.114044000         8.3809
10.232.4.101         <-> 10.235.8.8                92 7,999 bytes      79 20 kB         171 28 kB         0.000000000         8.5503
10.235.8.8           <-> 10.232.4.102              49 16 kB          62 5,581 bytes     111 22 kB         0.138301000         8.3566
10.235.8.8           <-> 10.235.8.8                 0 0 bytes        96 18 kB          96 18 kB         0.138327000         8.3566
127.0.0.1            <-> 127.0.0.1                  0 0 bytes        56 4,204 bytes      56 4,204 bytes     0.463964000         5.0367
================================================================================

$ tshark -r $PCAP_FILE -q -z conv,tcp | head
================================================================================
TCP Conversations
Filter:<No Filter>
                                                           |       <-      | |       ->      | |     Total     |    Relative    |   Duration   |
                                                           | Frames  Bytes | | Frames  Bytes | | Frames  Bytes |      Start     |              |
10.232.4.101:6379          <-> 10.235.8.8:37806                48 3,642 bytes      48 9,609 bytes      96 13 kB         0.000000000         8.4949
10.232.4.102:6379          <-> 10.235.8.8:49648                36 2,448 bytes      36 10 kB          72 13 kB         0.143919000         8.3510
10.232.4.103:6379          <-> 10.235.8.8:38996                36 2,448 bytes      36 10 kB          72 13 kB         0.143965000         8.3510
10.235.8.8:6379            <-> 10.235.8.8:52978                27 1,836 bytes      27 8,230 bytes      54 10 kB         0.143990000         8.3509
10.235.8.8:6379            <-> 10.232.4.103:43333              27 1,836 bytes      27 8,230 bytes      54 10 kB         0.144002000         8.3510

$ tshark -r $PCAP_FILE -T fields -e tcp.flags.str | sort | uniq -c
    284 ·······A····
      8 ·······A···F
    344 ·······AP···
      4 ·······A··S·
      4 ··········S·

$ tshark -r $PCAP_FILE -Y 'tcp.flags.syn == 1' -T fields -e frame.time -e tcp.flags.str -e ip.src -e ip.dst -e tcp.srcport -e tcp.dstport | head -n4
May 20, 2022 22:44:50.961767000 UTC ··········S· 127.0.0.1 127.0.0.1 39114 6379
May 20, 2022 22:44:50.961774000 UTC ·······A··S· 127.0.0.1 127.0.0.1 6379 39114
May 20, 2022 22:44:50.994887000 UTC ··········S· 127.0.0.1 127.0.0.1 39116 6379
May 20, 2022 22:44:50.994896000 UTC ·······A··S· 127.0.0.1 127.0.0.1 6379 39116

$ wireshark -r $PCAP_FILE -Y 'ip.addr == 127.0.0.1 && tcp.port == 39114 && tcp.port == 6379'
```

## Misc other resource usage observability tools on a GKE node

Sometimes we need to run ad hoc observations of a running container, but its image may lack the required tooling.
In such cases we can either install and run the tool outside of the target container or add it to the container.

Both of those options have trade-offs and depending on the circumstances either may be impractical or undesirable.
For example, adding a tool to a container implicitly gives it the same context and isolation properties as the
processes to be observed, but the tool may also have conflicting library dependencies or require elevated privileges.
Conversely, installing and running a tool from outside the target container means it lacks visibility into the
container's mount namespace, and consequently cannot resolve paths or inspect files within the container.
There are sometimes work-arounds for these problems (e.g. statically linking the tool before copying it into
the container to avoid library conflicts; using tools that natively switch namespaces when needed, etc.),
but these solutions are not always convenient or supported.

For each of the following tools, we show installation, usage, and known gotchas for both running the tool
and interpreting its output.

### Using `vmstat`

`vmstat` reports host-level resource usage statistics.

`vmstat` is not container-aware.  Typically it reports host-level utilization metrics
whether or not it is run inside a container.

Usually you want to ignore its first line of output, since that represents
averages since the last reboot.  All subsequent measurements are real-time averages
for the requested interval seconds.

To install and run `vmstat` using `toolbox`, run the following on the GKE node:

```
Install vmstat.
$ toolbox apt update -y
$ toolbox apt install -y procps
$ toolbox which vmstat

Run vmstat via toolbox, using a 1-second interval 3 times.
$ toolbox vmstat --wide 1 3
```

### Using `pidstat`

`pidstat` gathers and reports process-level statistics, covering many of the same metrics as `sar`.

To install and run `pidstat` using `toolbox`, run the following on the GKE node:

```
Install pidstat.
$ toolbox apt update -y
$ toolbox apt install -y sysstat
$ toolbox which pidstat

Choose a target host PID (not a container PID).
This can optionally be a comma-delimited list of PIDs, as shown here.
$ TARGET_PID_LIST=$( pgrep -f 'puma: cluster worker' | tr '\n' ',' )

Run pidstat via toolbox for the chosen PIDs, using a 1-second interval 3 times.
$ toolbox pidstat -p $TARGET_PID_LIST 1 3

Run pidstat, matching processes on their full command line (rather than specifying PIDs).
$ toolbox pidstat -l -G 'puma: cluster worker'

Show all threads for a matching PID.
$ toolbox pidstat -t -p $TARGET_PID 1 3
```

#### Tips for interpreting `pidstat` output

* `pidstat` is not aware of cgroup limits.
  * CPU utilization percentage represents mean CPU time / wallclock time during the interval.
* CPU utilization can exceed 100% if a process has multiple threads concurrently running on CPUs.
* Even a completely CPU-bound process may not reach 100% utilization if it is starved for CPU time by:
  * the container's cgroup limit being budgeted less than 1 CPU core
  * competing processes within the container using CPU time
  * competing processes outside the container using CPU time, if the host is oversubscribed (which is common)

#### Background and demo: Which PID to use for a process?

`pidstat` can be run either inside or outside of the target container, but since it is usually not included
by default, here we show how to run it from outside of the target container using `toolbox`.

The same process can have a different identifier (PID) in each PID namespace, and for tools like `pidstat`
(or `ps`, etc.) that take a PID as an argument, we must give them the PID that the target process uses
in the namespace where we are running the tool.

```
# Make a toy process to observe from inside and outside the target container.

msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ CONTAINER_ID=$( crictl ps --name webservice --latest --quiet )
msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ crictl exec $CONTAINER_ID sleep 123 &

# Find the process's PID from inside and outside the container.

msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ crictl exec $CONTAINER_ID pgrep -n -a -f 'sleep 123'
1089 sleep 123

msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ pgrep -n -a -f 'sleep 123'
789724 sleep 123

# Must use the host namespace's PID when running pidstat.

msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ toolbox pidstat -p 1089 1 3
Linux 5.4.170+ (gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl)  05/24/22  _x86_64_ (30 CPU)

23:25:37      UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command

msmiley@gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl ~ $ toolbox pidstat -p 789724 1 3
Linux 5.4.170+ (gke-gprd-us-east1-b-api-2-c1ce60b7-mfxl)  05/24/22  _x86_64_ (30 CPU)

23:25:44      UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
23:25:45     1000    789724    0.00    0.00    0.00    0.00    0.00     1  sleep
23:25:46     1000    789724    0.00    0.00    0.00    0.00    0.00     1  sleep
23:25:47     1000    789724    0.00    0.00    0.00    0.00    0.00     1  sleep
Average:     1000    789724    0.00    0.00    0.00    0.00    0.00     -  sleep
```

#### How does `pidstat` represent container CPU limit

`pidstat` reports CPU utilisation as used CPU seconds divided by wallclock seconds. It is not aware of container cgroup CPU quotas.

When a container's CFS quota runs out, the wallclock time spent stalled waiting for the quota to refill is reported by `pidstat` as `%wait`. The process remains runnable (state `R`) throughout — the kernel schedules it off the CPU until the quota refills every 100 ms.

##### Demo

This demo runs on a local Linux workstation with Docker on cgroup v1. It walks through starving a CPU-bound process by reducing its container's CFS quota and shows the effect in `pidstat`.

> [!note]
> cgroup v1 is deprecated in Kubernetes 1.31 and removed in 1.35. On cgroup v2 (default from GKE 1.33 and on modern workstations) the equivalent controls live in a single `cpu.max` file — under `/sys/fs/cgroup/system.slice/docker-<id>.scope/` on a workstation, or `/sys/fs/cgroup/kubepods.slice/.../cri-containerd-<id>.scope/` on a GKE node. Format is `<max> <period>`, where `max` means unlimited. See [Migrate to cgroupv2](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/migrate-cgroupv2).

Create a CPU-bound process in a container:

```sh
docker run -it --rm --name test_cpu_quota_starvation ubuntu:latest \
  /bin/bash -c 'while true ; do foo=1 ; done'
```

In another shell, find the container id and its PID from the host namespace:

```sh
CONTAINER_ID=$( docker ps --quiet --no-trunc --filter 'name=test_cpu_quota_starvation' )
TARGET_PID=$( cat "/sys/fs/cgroup/cpu/docker/$CONTAINER_ID/cgroup.procs" | head -n1 )
```

Initially the process uses a whole CPU:

```console
$ pidstat -p $TARGET_PID 1 3
Linux 5.13.0-41-generic (saoirse)  05/25/2022  _x86_64_ (8 CPU)

10:51:39 PM   UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
10:51:40 PM     0    161603  100.00    1.00    0.00    1.00  101.00     3  bash
10:51:41 PM     0    161603   99.00    0.00    0.00    0.00   99.00     3  bash
10:51:42 PM     0    161603  100.00    0.00    0.00    0.00  100.00     3  bash
Average:        0    161603   99.67    0.33    0.00    0.33  100.00     -  bash
```

Read the current CFS parameters — `-1` means unlimited:

```console
$ grep '' /sys/fs/cgroup/cpu/docker/$CONTAINER_ID/cpu.cfs_*
/sys/fs/cgroup/cpu/docker/805b4538…/cpu.cfs_period_us:100000
/sys/fs/cgroup/cpu/docker/805b4538…/cpu.cfs_quota_us:-1
```

Cap the container at 700 millicores (70K us of CPU per 100K us of wallclock):

```sh
echo 70000 | sudo tee /sys/fs/cgroup/cpu/docker/$CONTAINER_ID/cpu.cfs_quota_us
```

Now `pidstat` shows the process on CPU 70% of the time and stalled (`%wait`) the remaining 30% while waiting for the quota to refill:

```console
$ pidstat -p $TARGET_PID 1 3
Linux 5.13.0-41-generic (saoirse)  05/25/2022  _x86_64_ (8 CPU)

10:54:35 PM   UID       PID    %usr %system  %guest   %wait    %CPU   CPU  Command
10:54:36 PM     0    161603   70.00    0.00    0.00   30.00   70.00     6  bash
10:54:37 PM     0    161603   70.00    0.00    0.00   30.00   70.00     6  bash
10:54:38 PM     0    161603   70.00    0.00    0.00   31.00   70.00     6  bash
Average:        0    161603   70.00    0.00    0.00   30.33   70.00     -  bash
```

The process is runnable (state `R`) the entire time — it is scheduled off the CPU by the kernel, not blocked on I/O:

```console
$ for i in $( seq 100 ) ; do sleep 0.01 ; ps -o s= $TARGET_PID ; done | sort | uniq -c
    100 R
```

Clean up:

```sh
docker stop test_cpu_quota_starvation
```
