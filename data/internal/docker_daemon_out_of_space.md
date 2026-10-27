# Docker & Containerd Runbook: "No Space Left on Device" Incident Triage

## Overview & Symptoms
When building container images, pulling base layers, or launching CI/CD runner jobs, Docker or containerd fails with:
```text
failed to register layer: write /var/lib/docker/overlay2/...: no space left on device
Error response from daemon: mkdir /var/lib/docker/tmp: no space left on device
```
- **Scope:** CI/CD Build agents (GitHub Actions runners, Jenkins nodes), local developer workstations, and Docker hosts.
- **Impact:** Failed continuous integration builds, blocked deployments, and hung pipeline jobs.

## Immediate Diagnostic Checklist

### 1. Check Filesystem Disk and Inode Usage
```bash
# Check block space usage
df -h /var/lib/docker
# Check inode saturation (crucial: inodes can hit 100% even if disk space is free)
df -i /var/lib/docker
```

### 2. Inspect Docker Disk Footprint Breakdown
```bash
docker system df -v
```
Examine reclaimable space across:
- **Images:** Unused dangling layers (`<none>:<none>`).
- **Containers:** Stopped or exited container write layers.
- **Local Volumes:** Orphaned anonymous data volumes.
- **Build Cache:** BuildKit intermediate layer cache.

## Immediate Recovery Steps

### 1. Emergency System Prune (Instant Space Reclamation)
Run deep prune to clean unreferenced images, stopped containers, and build cache:
```bash
# Prune all stopped containers, unused networks, and dangling images
docker system prune -f --volumes

# Deep build cache purge (often reclaims 10GB - 50GB in CI hosts)
docker builder prune -a -f
```

### 2. Identify and Purge Runaway Log Files
Containers without log rotation (`json-file` default) can grow log files indefinitely in `/var/lib/docker/containers/<id>/`:
```bash
# Find top 5 largest container json logs
find /var/lib/docker/containers/ -name "*-json.log" -exec du -h {} + | sort -hr | head -n 5

# Safely truncate (do NOT delete) active open log files
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

## Permanent Fix & Docker Daemon Configuration

Configure log rotation and storage quota in `/etc/docker/daemon.json`:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
```
Restart Docker service to apply:
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

## Scheduled Maintenance Cron
On dedicated CI runner nodes, schedule automated nightly prune jobs:
```bash
0 2 * * * docker system prune -a -f --filter "until=48h"
```
