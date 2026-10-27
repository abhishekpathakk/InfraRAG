# macOS Runner Performance

This document covers the I/O performance characteristics of the macOS runner fleet: how the two EBS volumes on each host are used, what the hardware limits actually are, why the current settings were chosen, and how to measure any of it on a live host.

For debugging non-performance issues see [debugging.md](./debugging.md). For where the AWS resources live see [resources.md](./resources.md).

## EBS volume layout

Each macOS host has two EBS volumes with distinct roles:

- **Root volume** (100 GiB): restored from the host AMI snapshot. Heavily read during boot, close to idle afterwards.
- **Secondary volume** (750 GiB): created empty, formatted as an APFS volume named `VMData` on first boot, and holds the job VM image downloads and running job VMs.

Historical I/O variance ([job VM Performance Variance](https://gitlab.com/gitlab-org/ci-cd/shared-runners/infrastructure/-/issues/223)) was traced to EBS lazy loading of large AMI images, back when all job VMs were baked into the host AMI. The current split addresses this **for the job VM data volume** by:

1. Using dedicated EBS volumes for job VM disks
1. Pre-downloading images at startup
1. Ensuring full EBS performance from the start

That volume is created empty rather than restored from a snapshot, so it carries no lazy-loading penalty. See [image building challenges](./image_building.md#image-building-challenges) for the history behind that decision.

The root volume is a different case: it is still restored from a snapshot, so it still pays a hydration cost on first boot. See [root volume throughput](#root-volume-throughput).

## Instance EBS ceilings

The instance's EBS bandwidth is a single budget **shared across both volumes**, so provisioning them independently does not give each its own allowance:

| Instance type | EBS bandwidth | Max throughput | Max IOPS (16 KiB) |
| --- | --- | --- | --- |
| `mac2.metal` (M1) | 10,000 Mbps | 1,250 MB/s | 55,000 |
| `mac2-m2pro.metal` (M2 Pro) | 8,000 Mbps | 1,000 MB/s | 55,000 |

Two properties of this are easy to get wrong:

- **The larger machine has the smaller pipe.** `mac2-m2pro.metal` has 20% less EBS bandwidth than `mac2.metal` despite having more CPU and memory. EBS bandwidth on EC2 Mac is a property of the Nitro-over-Thunderbolt attachment rather than the SoC, so storage must not be sized from the compute tier.
- **The two sides use different units.** Provisioned volume throughput is specified in MiB/s, while AWS quotes instance ceilings in MB/s derived from the bit rate. For `mac2-m2pro.metal`, 8,000 Mbps = 1,000 MB/s = 954 MiB/s, so a volume provisioned at 1,000 MiB/s cannot deliver its full rate on that instance type.

Reaching the ceiling requires concurrency. A single sequential reader is latency-bound at roughly 170 MB/s, and roughly 7 to 8 parallel streams are needed to saturate the instance budget.

- [EBS-optimized instance types](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html)
- [EC2 Mac instance considerations](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)

## Root volume throughput

**The root volume's provisioned throughput should not be reduced.** It is restored from the host AMI snapshot, so its blocks are hydrated from S3 on first access at a rate bounded by the volume's provisioned throughput. macOS boot also reads the root volume concurrently across many services, so it consumes far more bandwidth than a single-stream measurement suggests.

The root volume looks idle in steady state, which makes its provisioned throughput appear wasted. It is not. Three configurations measured end to end on `saas-macos-staging` (`mac2-m2pro.metal`, same AMI, August 2026):

| Root volume | Boot to downloads start | Boot to nesting ready | Root read throughput | Cost per instance-month |
| --- | --- | --- | --- | --- |
| 750 MiB/s / 3,000 IOPS | 36s | 291s | ~786 MB/s | $25 |
| 125 MiB/s / 3,000 IOPS | 113s | 374s | 131 MB/s | $0 |
| 400 MiB/s / 10,000 IOPS | 49s | 293s | 419 MB/s | $46 |

The regression sits entirely in the pre-download phase. The image pull is unaffected (251s, 257s and 239s respectively).

AWS's general recommendation of 10,000 IOPS and 400 MiB/s for EC2 Mac instances measured both slower and more expensive here than the 750 MiB/s / 3,000 IOPS the shards run, so treat it as a floor rather than a target for this workload. Boot on this path is throughput-driven rather than IOPS-driven, and the extra 7,000 IOPS did not compensate for the lost bandwidth. First-touch reads on the snapshot-restored root volume are measurably slower than later reads of the same blocks, which adds to the cost of a slow root volume on first boot. The size of that penalty has not been isolated, so it is not quantified here: the available measurements varied provisioned throughput and hydration state together, and EBS burst credit inflated the first run of each test.

750 MiB/s / 3,000 IOPS is additionally the cost-optimal setting for a throughput-bound gp3 volume: 3,000 IOPS is the free baseline, and the ratio limit of 0.25 MiB/s per provisioned IOPS makes 750 MiB/s the most throughput obtainable without paying for any IOPS.

### Low throughput warning: Instances fail readiness and dedicated hosts accumulate

Starving root volume throughput does not only slow startup. While the staging root volume was set to 125 MiB/s for roughly 24 hours, we witnessed many failed instance launches.

Because `auto_release_hosts` is `false` and Mac dedicated hosts carry a 24 hour minimum allocation, every replacement for a failed instance consumes an additional dedicated host that cannot be released promptly. At roughly $1,000 per host-month (see [dedicated host limitations](./dedicated_hosts.md#dedicated-host-limitations)) this is far more expensive than any saving available from trimming volume settings, and it can exhaust a shard's host pool entirely.

## Job image pull

The pull runs one `s3pipe | zstd -d | tar -xf` pipeline per image in parallel, which is what gives it enough concurrency to use the instance's bandwidth. Measured on a `mac2-m2pro.metal` staging host pulling two ~75 GiB images:

- ~640 MiB/s aggregate write throughput, roughly 320 MiB/s per pipeline
- 150 GiB written in 251s
- Boot to nesting ready 291s, against the ASG `health_check_grace_period` of 600s

Shards configured with three images run three pipelines and scale accordingly. Pull duration is **not** sensitive to the secondary volume's provisioned IOPS: it measured 251s at 6,000 IOPS and 257s and 239s at 16,000. The pull is throughput-shaped, issuing roughly 250 KiB I/Os at around 2,700 IOPS, so it never approaches the IOPS ceiling.

## Secondary volume (VMData) IOPS

For random I/O the binding constraint is the volume's provisioned IOPS rather than bandwidth. Measured with `fio` inside nested job VMs on `mac2-m2pro.metal`:

| Provisioned IOPS | 1 VM randwrite | 1 VM randread | 2 VM randwrite | 2 VM randread |
| --- | --- | --- | --- | --- |
| 6,000 | 6,000 (flat) | 6,000 (flat) | not tested | not tested |
| 16,000 | 7,190 (flat) | 9,790 (flat) | ~14,020 | ~14,200 |

At 6,000 both reads and writes pinned to the *identical* dead-flat figure despite very different I/O profiles, which is the signature of a volume throttle. At 16,000 they plateau at different values and fluctuate, so the constraint has moved to the virtualisation I/O path at roughly 14,000 aggregate IOPS across two VMs. Provisioning above 16,000 would therefore buy nothing.

Two details worth knowing:

- **Writes are amplified.** Guest 4 KiB random writes surface as 16 KiB host I/Os because Apple silicon uses a 16 KiB page size, costing roughly two host EBS IOPS per guest write. Reads pass through 1:1.
- **Bandwidth is nowhere near the limit during random I/O**: 56 MB/s read and 220 MB/s write against a ~1,000 MB/s instance ceiling. The secondary volume's provisioned throughput exists for the sequential image pull, not for job I/O.

The figures above come from `fio` with `--direct=1`, which is a deliberately IOPS-maximising synthetic workload. Real builds mostly issue buffered I/O, which APFS coalesces into roughly 250 KiB host I/Os at around 1,250 host IOPS, so a real jobs demand is far lower. Whether 16,000 is larger than production needs is an open question that requires `VolumeWriteOps` and `VolumeReadOps` percentiles from a production shard over real job traffic.

## Measuring EBS performance

### Identify the volumes first

Device enumeration is **not stable across boots**. Confirm device mapping before running any tests:

```shell
# On the host Mac
system_profiler SPNVMeDataType | grep -E "Amazon Elastic|Capacity|BSD Name"
diskutil list | grep -E "^/dev/disk|Physical Store|VMData"
```

The ~107 GB device is the root volume. The ~805 GB device backs `/Volumes/VMData`.

### Sample host-side I/O

```shell
# On the host Mac, substituting the devices identified above
iostat -d -w 2 disk4 disk5
```

Interpreting the output:

- A **dead-flat** `tps` figure means the volume's provisioned IOPS limit is throttling. Reads and writes pinning to the same number despite very different I/O profiles is the clearest signal.
- A **fluctuating plateau** means the limit is elsewhere.
- `KB/t` shows the effective I/O size.

### Benchmark from inside a job VM

`fio` is not present in the job images. A nested VM is an APFS clone that is discarded on `nesting delete`, so installing tooling inside one does not modify the base job image. See [managing nested job VMs](./debugging.md#managing-nested-job-vms-with-nesting-client) for creating one and finding its port.

```shell
# Inside the job VM
HOMEBREW_NO_AUTO_UPDATE=1 /opt/homebrew/bin/brew install fio

# Random write, bypassing the guest page cache
/opt/homebrew/bin/fio --name=rw4k --directory=/Users/gitlab --rw=randwrite \
  --bs=4k --size=1G --numjobs=4 --iodepth=32 --direct=1 \
  --ioengine=posixaio --runtime=30 --time_based --group_reporting
```

`--direct=1` maps to `F_NOCACHE` on macOS. Without it the guest page cache absorbs the writes and the host volume sees almost nothing. Buffered tools such as `dd` are unsuitable for measuring IOPS for the same reason, and because APFS coalesces small buffered writes into roughly 250 KiB host I/Os.

### Measuring raw volume throughput

Raw reads from `/dev/rdiskN` bypass the APFS buffer cache. **Only ever read from a raw device.** Transposing `if=` and `of=` in the command below writes zeroes over the volume and destroys it.

```shell
# On the host Mac, 8 parallel streams to defeat the single-stream latency limit
for s in 0 2048 4096 6144 8192 10240 12288 14336; do
  sudo dd if=/dev/rdiskN of=/dev/null bs=1m count=1024 skip=$s 2>&1 | tail -1 &
done; wait
```

Sum the reported rates, or divide 8 GiB by the wall time. A single `dd` measures per-request latency rather than bandwidth and will substantially understate the volume. Discard the first run and use a window of at least 30 seconds: after an idle period EBS allows a brief overshoot above the provisioned rate, and on a 125 MiB/s volume the first run measured 10% high while the two following it sat exactly at the cap. On a freshly launched instance the first pass over the root volume also includes snapshot hydration, which skews the other way.
