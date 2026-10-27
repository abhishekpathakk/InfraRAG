# Gitaly profiling

## Gitaly process

Gitally is written in Go which has [built in profiling](https://go.dev/blog/pprof).

A convenient way is to use ssh port forwarding to download the profiles
directly to your own workstation. The actual Gitaly port (`9236`) can be found
[here](https://prometheus.gprd.gitlab.net/targets#job-gitaly). We are
forwarding this to our local port `6060` as this is the standard port for go
pprof endpoints.

```shell
ssh -N -L 6060:localhost:9236 file-03-stor-gprd.c.gitlab-production.internal
```

```shell
# fetch 30 seconds of CPU profiling
curl -o cpu.bin 'http://localhost:6060/debug/pprof/profile'
go tool pprof -http :8080 cpu.bin

# fetch 5 seconds of execution trace (this will have a performance impact)
curl -o trace.bin 'http://localhost:6060/debug/pprof/trace?seconds=5'
go tool trace trace.bin

# fetch a heap profile to profile memory usage
curl -o heap.bin 'http://localhost:6060/debug/pprof/heap'
go tool pprof -http :8080 heap.bin

# fetch a list of running goroutines
curl -o goroutines.txt 'http://localhost:6060/debug/pprof/goroutine?debug=2'
```

## GCP Profiling

[GCP
profiles](https://console.cloud.google.com/profiler/gitaly/cpu&project=gitlab-production)
are also available service wide.

## System CPU Profile

Since Gitaly shells out to `git` the Go profile is not enough information. We
can use Linux built in [`perf`
tool](../tutorials/how_to_use_flamegraphs_for_perf_profiling.md)

```
# All processes
steve@file-01-stor-gstg.c.gitlab-staging-1.internal:~$ perf_flamegraph_for_all_running_processes.sh

# Specific Process
steve@file-01-stor-gstg.c.gitlab-staging-1.internal:~$ perf_flamegraph_for_pid.sh 12

# For user
steve@file-01-stor-gstg.c.gitlab-staging-1.internal:~$ perf_flamegraph_for_user.sh git
```

## Periodic System CPU Profiles

We run CPU profiles at a periodic internal and upload these to
[`gs://gitlab-gprd-periodic-host-profile`](https://console.cloud.google.com/storage/browser/gitlab-gprd-periodic-host-profile;tab=objects?forceOnBucketsSortingFiltering=true&project=gitlab-production&prefix=&forceOnObjectsSortingFiltering=false)
where you can choose a hostname and a specific time.
