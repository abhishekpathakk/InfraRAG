# Host clock skew / clock not synchronising

`HostClockSkew` or `HostClockNotSynchronising` is firing. A host's clock has
drifted from true time, or its NTP client has stopped synchronising. This can
break TLS validation, token/expiry checks, database replication, and make logs
across hosts line up wrong, so it's worth chasing down even at s3.

GitLab hosts sync time with chrony (`chronyd`), configured by Chef via the
`gitlab-server::ntp-client` recipe. Config lives at `/etc/chrony/chrony.conf`.

## 1. Find the host and confirm it's real

The alert labels carry the `instance`. Check the offending host's metrics in
the relevant tenant (substitute `<host>`):

```promql
node_timex_offset_seconds{instance="<host>"}    # offset from true time; > ~0.05s sustained is abnormal
node_timex_sync_status{instance="<host>"}        # 0 = kernel clock NOT synchronised
node_timex_maxerror_seconds{instance="<host>"}   # grows as sync is lost
```

The Node Exporter Full dashboard (`rYdddlPWk/node-exporter-full`, "Time"
panels) shows the same series; the alert annotation links straight to it.

A single host with a small, recovering offset is usually noise. A host stuck at
`sync_status == 0`, or offset climbing and not coming back, is real.

## 2. Is this a Chef VM or a GKE node?

The remediation is different, so check the `instance`/`fqdn` first:

- **Chef-managed VM** (e.g. `*.c.gitlab-production.internal`): you can SSH in and
  fix chrony directly. Go to step 3.
- **GKE node** (e.g. `gke-*`): these run Container-Optimized OS and are managed
  by GCP. You don't hand-fix time on them. Skip to step 4.

If multiple hosts are skewing at once, don't bother per-host; that points at an
upstream NTP or network problem. Go to step 4.

## 3. Fix chrony on a Chef VM

SSH to the host and check the daemon:

```bash
systemctl status chronyd.service
chronyc tracking      # look at System time, Leap status (should be "Normal"), Stratum
chronyc sources -v    # are upstream sources reachable and selected?
```

Common cases:

- **`chronyd` is dead or wedged** → `sudo systemctl restart chronyd.service`,
  then re-check `chronyc tracking`. The offset should start converging.
- **Daemon up but sources unreachable** → likely a network/firewall issue
  reaching the upstream NTP servers (defined in `/etc/chrony/chrony.conf`). This
  is not a host-local fix, so go to step 4.
- **Host recently rebuilt/restored/cloned with a bad clock** → a `chronyd`
  restart usually lets it step the clock back into line.

If a restart fixes it and it stays fixed, you're done. If it drifts again,
escalate. The config or the upstream is the problem, not the daemon.

## 4. When you can't fix it host-side

Escalate to the owning team / SRE on-call (these alerts are `severity: s3`,
`team: sre_reliability`) when:

- It's a **GKE node**: flag it; the node is GCP-managed. If it's causing real
  impact, cordon/drain and let the node be recycled rather than trying to fix
  time in place.
- **Multiple hosts** are skewing together: treat it as an upstream NTP or
  network incident, not a per-host fault.
- A Chef VM's `chronyd` is healthy but the clock won't converge, or it drifts
  again after a restart. The upstream source or `chrony.conf` needs attention,
  which goes through Chef.
