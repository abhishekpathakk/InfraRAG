# Filesystem errors are reported in LOG files

## Symptoms

You're likely here because you saw a message saying "Really low disk space left on _path_ on _host_: _very low number_%".

## Investigation

> [!note]
> The `fqdn` and `device` may be discoverable through an explore link on the alert.

SSH to the affected machine and validate disk usage using `df`.

```
$ df -h
Filesystem      Size  Used Avail Use% Mounted on
/dev/root        39G   39G  328K 100% /
/dev/sdc         50G   14G   36G  27% /var/log
...
```

With a confirmed mountpoint we can iterate to the source of our usage
using `du`.  In this case we have `100%` usage on `/dev/root` (`/`) so we start
there and expand `/` as we find the largest directories.

```
sudo du --max-depth 1 -x -h /
```

### Performance capture investigation

For performance captures that have grown excessively large we should
attempt to capture a performance profile to investigate the issue.

#### Copy the performance capture

We should move the file to an alternative filesystem mount where space is available.

If there is no space available on existing disks and there are no
service interruptions caused by the disk usage adding a new disk to
the node for the investigation may be a viable option:
<https://docs.cloud.google.com/compute/docs/disks/attach-disks>

#### Profile the performance capture

> [!note]
> More details can be found in this [tutorial](../tutorials/how_to_use_flamegraphs_for_perf_profiling.md#the-easy-way-helper-scripts).

Once we have the PID for `perf record` we can use this with
`perf_flamegraph_for_pid.sh` to capture the profile for the record.

```
perf_flamegraph_for_pid.sh PID_TO_PROFILE
```

We should retain the output for later analysis.

## Resolution

### Removing large files

If the source of the disk usage is one, or a number of files that are
confirmed to be non-critical we can clean these up.

> [!note]
> This is the case for log files that are not rotated and performance captures.

We can typically clean up the files using `rm` as usual to free space on the disk.

Confirm that the disk usage has dropped using `df -h` as in the investigation steps.

If the disk usage remains the same the file is likely being held open by a process. We can discover this using `lsof`.

```
sudo lsof /path/to/deleted/file
```

We should confirm that the process is safe to kill, and then if so,
proceed with killing the process to allow the file to be deleted.

### Expanding a disk in GCP

As a last resort you may need to expand either a persistent or root volume in
GCP. This can be done online for persistent mounted disks and root volumes. In
the case of root volumes terraform will try to recreate the resource so it will
need to be done in the console manually, and then made in terraform.

* Make the adjustment in terraform or the console to for the disk, this can be
  done while the instance is running.
* run `sudo lsblk` to see that the new space is available:
Example:

```
$ sudo lsblk
NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sdb      8:16   0   50G  0 disk /var/log
sda      8:0    0  100G  0 disk
└─sda1   8:1    0   20G  0 part /
```

* run `growpart <device> <partition number>` to increase the partition to the
  space available. **Note that there is a space between the device and the
  partition number.**.

```
## Root volume example
sudo growpart /dev/sda 1
```

* confirm that the space is now taken with `sudo lsblk`.
Example:

```
$ sudo lsblk
NAME   MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT
sdb      8:16   0   50G  0 disk /var/log
sda      8:0    0  100G  0 disk
└─sda1   8:1    0  100G  0 part /
```

* Resize the filesystem to use the new space with `sudo resize2fs <partition>`.
Example:

```
resize2fs /dev/sda1
```
