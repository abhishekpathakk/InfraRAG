# A survival guide for SREs to working with Sidekiq at GitLab

## What is Sidekiq and why do we use it?

Sidekiq is a background job processor for Ruby-on-Rails (arguably the most well
known/popular one, although there are others). We use it to pull processing out of the web and API tiers, to keep the
responsiveness of web requests acceptable for our users by keeping our front-end fleet workers (of which we have a
limited number) being kept busy waiting on 3rd party services with unknown and unpredictable latency and delays. The
classic example is sending e-mails in response to user actions, but GitLab also uses background jobs for other local
tasks that are time critical but which are better served by being extracted from the main web request cycle e.g. merging.

## Definitions

These will be explained in more detail as we go, but to provide a little heads-up:

* Job: A request to run a bit of Ruby code to perform a specific operation on specific data (e.g. send a webhook for an
  event on a project, start a CI pipeline, etc)
* Queue: A Redis structure that holds Jobs waiting to execute
* Worker: A running instance of Rails that executes Jobs retrieved from a Queue
* Shard: A set of Workers that executes Jobs from one or more Queues of Jobs with some common characteristics

## How do jobs get into Sidekiq

Sidekiq uses Redis as its datastore, because it has excellent [performance
characteristics](https://github.com/sidekiq/sidekiq/wiki/FAQ#wouldnt-it-be-awesome-if-sidekiq-supported-mongodb-postgresql-mysql-sqs--for-persistence)
for the Sidekiq use case. Sidekiq can put jobs into named 'queues', and by default the only queue is one called
'default'. GitLab, however, uses more than one queue.  By default there is one queue per Worker class (a historical decision
to help with workload management/queuing at scale), but [Routing Rules](#routing-rules) means that this is no longer
the only way, and arbitrary groups of jobs can be routed to arbitrarily named queues.  Indeed, for .com
(gprd/gstg at least) we exclusively use routing rules, and other than a small handful of special cases which still have a queue-per-worker,
we use a single queue per [shard](#shards).

Client side Ruby code, typically in the web or API tiers, uses the Sidekiq client gem to request that a certain 'Worker'
class be executed (an instance created and the `perform` method called) with a set of arguments. The Sidekiq client
serializes the job request to a JSON string which is added to a per-queue
[LIST](https://redis.io/topics/data-types#lists) in Redis, under the key `resque:gitlab:queue:QUEUE_NAME`.

To decide on the queue name, the [Routing Rules](#routing-rules) are consulted in order until there is a match.

Regarding the serialization:

1. The job definition in Redis contains the class name as well as the arguments, and putting a job for
   `FooWorker` in the queue `bar` will execute correctly in any Sidekiq worker configured to look at the queue `bar` (assuming
   the code for FooWorker exists on that Sidekiq deployment)
1. The arguments for the Worker `perform` method must be able to be encoded to JSON safely. This means that Ruby objects
   are not allowed (well, it's possible if you try really hard, but just don't, it'll end badly). Typically they'll be
   simple strings, or the database primary key for the row/object that the worker should work on; the Sidekiq worker
   will then fetch that object from the DB and perform the requested operation on it.  The arguments are (hopefully
   obviously) order-dependent, so the order seen in the JSON (and as logged) is important to consider when reviewing
   what the code will do.

### Routing rules

* Syntax: <https://docs.gitlab.com/administration/sidekiq/processing_specific_job_classes/>
* Current configuration (gprd):
  * Search `routingRules` in <https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/gprd.yaml.gotmpl>
  * Search `routing_rules` in <https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/gprd-base.json>

These should be configured identically in chef and helm but there are no technical controls ensuring they are kept the same.
If they are not, then jobs *may* execute on the wrong shard, or not execute at all.  Divergence is only in exceptional
and likely transient situations where you can describe and reason out exactly what will happen and why that is necessary
(or: "you'll know when you know").
It is very important to remember that the routing rules are consulted when a job is submitted, which can be from anywhere
running Rails, including web, api, and Rails consoles, not just Sidekiq, so this repeated configuration will be required
until we eliminate all chef-configured VMs running Rails.

For .com the rules start with some special-case-worker handling, then a rule for each [shard](#shards), finished by a `*` rule
that routes all unmatched jobs to the `default` queue, which runs on the `catchall` shard.

At Rails boot time each worker class uses the routing rules to determine which queue it goes into, where each rule may use a queue
selector which is a boolean expression on the [job characteristics](#job-characteristics).

### Historical queue-per-worker

The default/unconfigured behavior has an implied route for all (`*`) to `nil/null` where nil means the per-worker autogenerated
queue name being the lower-snake-case of the Worker class name, without the Worker suffix. For example the `WebHookWorker` class would
be put in the `web_hook` queue, meaning there will be a JSON string entry pushed onto the `resque:gitlab:queue:web_hook` LIST.

There are also `namespaces` (colon separated, two parts only) e.g. The `NewReleaseWorker` has a queue\_namespace of
`notifications`, and in the default configuration gets put into a queue called `notifications:new_release`. This is a relic of previous
attempts to control where Sidekiq jobs run, where we used wildcards on namespaces, e.g. to make all the pipeline jobs
run on a pipeline fleet of VMs. It has no current effect.

### Redis

For gitlab.com we have a separate Redis cluster specifically for Sidekiq, split out in 2019. The workload is very
specific and we were running into problems sharing that load with our core 'persistent' (Shared State) Redis. Note
that this is not a cache-type Redis instance, and it does not evict keys when memory limits are reached, so if we have
too many (or overly large) queued jobs we could OOM the Redis cluster, which would be very bad. We have
[monitoring](https://dashboards.gitlab.net/d/alerts-sat_redis_memory/alerts-redis_memory-saturation-detail?orgId=1&var-PROMETHEUS_DS=Global&var-environment=gprd&var-type=redis-sidekiq&var-stage=main)
of this tied into our saturation alerting, so we should be made aware of this with plenty of time to spare. At this
writing, the memory saturation is below 5%, so there's plenty of headroom.

It may be interesting to read the [sidekiq style guide](https://docs.gitlab.com/development/sidekiq/)
for GitLab as that describes some of this in more detail, from a backend engineers perspective.

## How do jobs get picked up

At it's simplest, a Sidekiq (Ruby) process runs somewhere with all the same application code as the web
application. It is started with 'bundle exec sidekiq' which runs the 'sidekiq' CLI script from the Sidekiq gem; this
subscribes to a set of queues (Redis LISTs) named on the command line, pops jobs off those queues and executes them in
one of the worker threads by deserializing the JSON, finding the specified class, creating an instance of that class,
and calling `perform` on it with the arguments given in the JSON.

Aside: at this point you might have spotted a nasty corner case: the code base that created jobs and serialized/pushed
them into Redis needs to be *compatible* with the codebase running on Sidekiq. When these are different machines (for
scale, as in GitLab.com), there is an opportunity for odd behavior. For example, should the web app push a job with a
changed set of arguments, the workers may not be able to process them successfully; there are also other possible
failure modes, and having a canary web/api fleet is related to these. Changes to existing jobs need to be managed in a
similar way to how [DB migrations](https://docs.gitlab.com/development/sidekiq/) are, sometimes
requiring multiple releases to safely migrate with zero-downtime. This is discussed at [](https://docs.gitlab.com/development/sidekiq/compatibility_across_updates/)

### Sidekiq Cluster (historical)

Mostly not relevant to *gitlab.com* (gstg, gprd, pre) but possibly still occasionally useful for SREs working with
other deployments (e.g. ops)

In GitLab there are two ways that Sidekiq can run: legacy/traditional mode, and sidekiq-cluster.
The legacy mode has been removed from omnibus deployments and sidekiq-cluster is now the default, but that doesn't
matter to us because GitLab.com runs sidekiq exclusively in kubernetes, where the CNG Sidekiq docker image runs only a single
traditional mode Sidekiq process (see [Kubernetes](#kubernetes)), although it uses sidekiq-cluster in dry-run mode to
figure out what to run (a slight hack for convenience).

When in active use (not dry-run mode), sidekiq-cluster executes multiple (traditional gem) Sidekiq processes, with a
configurable concurrency (thread count) for each worker. The intention is to run one worker per CPU core, with a suitable
concurrency chosen depending on the workload (more to come on that later). The sidekiq-cluster process then monitors the
processes it created; if any die, it gracefully terminates the rest and exits, with the supervisor process then restarting
sidekiq-cluster.

### Kubernetes

Rather than running sidekiq-cluster and thus having an additional layer of supervision, we use Kubernetes to handle the
"multiple process" problem and run the traditional single Sidekiq Ruby/Rails process. We still have *concurrency* > 1
to maximize our CPU utilization, but that's threads not processes.

Side note: the docker container actually use sidekiq-cluster with the queue selector argument in dry-run mode to
generate a list of queues to pass to the single Sidekiq process, much as sidekiq-cluster would do if it were running
the sub-processes itself. This is just a startup step, and could plausibly be simplified in future.

Autoscaling ([Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/))
is interesting; it's not always practical. The primary issue is boot-time for a Sidekiq process. With some effort it's
now down to approximately 1 minute, however, some of our [shards](#shards) have workload profiles that are incompatible with this
because they drop many (hundreds or thousands) of jobs on the queue at once. With a fully provisioned set of VMs, the
jobs can often be completed within a minute or two. However in Kubernetes, if the workload was scaled down to some
smaller size, it will see the CPU usage caused by the existing workers getting busy and start spinning up more pods.
Additionally the startup process is CPU-intensive and takes a minute, and the additional load on the node while that
happens causes further scaling (while also slowing the original workers down a bit); this doesn't even consider
auto-scaling the node count. Then, after all that happens, it's not uncommon for the work to be completed by the time
all the new workers are ready. In short, boot times are too long and expensive to effectively autoscale some shards,
which we solve by sometimes having a fixed number of pods for a shard. Some shards do manage work well with this
(elasticsearch, particularly while we're doing backfill indexing of existing projects), and they are allowed to
autoscale, within limits. The list of shards and whether they autoscale or not may change with time, so they will not be
listed here. Simply be aware that there is variation, and this is an area of ongoing work.

Other than these matters, jobs are picked up and processed in exactly the same fashion in Kubernetes as on VMs.

### Shards

We need to tell sidekiq which queues to tell the individual Sidekiq processes to listen on. On gitlab.com in particular,
we want to split our Sidekiq processing up into individual workloads or `shards`, each of them processing some subset
of the Sidekiq jobs, to maintain control e.g.  limiting some types of jobs, and ensuring that jobs are being processed
fast enough for their urgency. Each workload/shard translates into a Kubernetes workload running a single Sidekiq
process per pod (with threaded concurrency, of course).

The distribution of jobs used to be complicated and manual, including things like queue namespaces and carefully
curated/counted configurations of queue names given to Sidekiq to get a certain number of workers available to run each
type of queue, on suitably provisioned VMs. This was fragile, easily misconfigured (e.g. queues running on multiple
different types of Sidekiq VMs), and difficult to reason about, particularly during incidents if capacity was limited by
our per-queue configuration but Sidekiq VMs were not actually busy.

So we created the [Routing rules](https://docs.gitlab.com/administration/sidekiq/processing_specific_job_classes/#routing-rules)
which uses the [execution characteristics](#job-characteristics) of jobs to select jobs allowing for a more effective
allocation of resources with more predictable and reliable effects. We choose
the threading concurrency for a shard carefully. For example, a shard that will be processing jobs with long
running external I/O (e.g. webhooks) can run with a high concurrency, as most of the time the Sidekiq thread will be
waiting on network I/O to 3rd parties. On the other hand, jobs running what we know to be locally CPU-bound jobs should
run at a much lower concurrency; while such jobs may still have times they're waiting on databases and can therefore have
concurrency a little over 1, those delays are much smaller so concurrency needs to be much lower.

Each of our Sidekiq `shards` runs only jobs that match a given selector, giving us the benefits noted above
(control + observability).  However, we implement this using [routing rules](#routing-rules) such that the shard
selection is done when the job is *scheduled* by the Sidekiq client by targeting a queue (arbitrarily) named the same
as the shard name.  Each shard generally only listens to that one queue name, other than a small handful of exceptions
where the name cannot be configured (e.g. mailroom with email_receiver), or where the job still requires it's own
queue for capacity management or similar purposes.  There should be comments in the k8s routing rules noting
the `why` for each such exception.

### Job Characteristics

To support the routing of jobs by characteristics, there is metadata included in the worker class (see [Sidekiq Style
Guide](https://docs.gitlab.com/development/sidekiq/)). A [rake
task](https://gitlab.com/gitlab-org/gitlab/-/blob/master/lib/tasks/gitlab/sidekiq.rake) looks for all the Sidekiq
workers in the code base and generates `app/workers/all_queues.yml` (and `ee/app/workers/all_queues.yml` for EE-specific
jobs).

The characteristics are well described in the Sidekiq style guide, but boil down to:

* urgency: how quickly must this job be picked up; `high` typically means a user is sitting at a UI action waiting on
  this job (e.g. a merge, or many CI pipeline jobs) whereas low urgency can be dealt with 'eventually'.
* resource-boundary: cpu, memory, or none: CPU implies it needs lower concurrency; memory means it needs to run in places
  with more memory allocated (e.g. project exports); these are mutually exclusive, and if neither applies, 'none' is the default

The urgency expectations flow into SLIs and SLOs, such that the nodes running high urgency jobs will alert when the
latency (waiting time) for jobs rises above a fairly low threshold, whereas low urgency jobs can wait for quite a bit
longer before alerts fire. These expectations are also manifested in apdex metrics for Sidekiq.

## Observability

### Dashboards

#### Sidekiq overview

Start at <https://dashboards.gitlab.net/d/sidekiq-main/sidekiq-overview?orgId=1>. This gives a high level view of how
Sidekiq is doing overall. Apdex is at the top which will likely have clear signals if "something" is wrong, but to get
quickly to useful information scroll down to the `Sidekiq Queues` section. The aggregated queue length is *one*
possible indicator of issues, although in certain cases we expect queuing (particularly elasticsearch indexing, during
initial indexing operations), so you need to look at the graphs for queue length and latency per job to see if (as is
usual) there's only a few jobs that are causing trouble. A little lower down, `Sidekiq Execution`/`Sidekiq Throughput per Job` can also be
useful to see if the current execution rate of jobs is unusual; this will inform whether any queuing is because there's
more jobs than usual, or if processing has ceased (the former is much more likely, but you never know)

On the `per Shard` graphs, left-clicking on one of the lines opens a menu from which the [Shard
Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail) dashboard for that shard can be
opened.

#### Shard Detail

The [Shard Detail](https://dashboards.gitlab.net/d/sidekiq-shard-detail/sidekiq-shard-detail) dashboard shows a more
focused view of graphs related to just jobs on the selected shard(s), including queue length (total and per job),
latencies, actively executing job counts, throughputs etc. The "Total Execution Time" panel may look a little odd at
first glance, but it's showing how many "execution seconds" were consumed by jobs on this shard across the fleet; if 5
jobs on a shard all started and ended at the same time, and ran for 5 seconds each (and were the only jobs on that shard
at the time), this would record 25 seconds on this datapoint when they end. With a busy shard with a lot of workers
overlapping in the normal fashion, this gives an indication of how heavily used this shard is. Note that this will show
different patterns from graphs like 'throughput' which are only counting numbers of jobs as this metric also reflects
job run time.

##### Shard Utilization Panel

Towards the bottom is a final slightly complicated panel: "Shard Utilization". This uses the same basic metric as
"Total Execution Time", but presents it as a proportion of available Sidekiq threads across the given shard. It was
empirically [found](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/2027#note_306791919) that the sweet spot
(the goldilocks zone) is between 23% and 43% utilization when there is sufficient capacity to handle load without
negatively affecting latency or execution time, without having too much slack unused capacity. This is represented with
the green zone; the graph being consistently under that zone indicates over-provisioning; being in the red zone
consistently indicates under-provisioning. Spikes and dips can occur without terrible effect, and having
non-auto-scaling VMs contributes to over-provisioning during quieter hours, but consistently being outside The Zone is
grounds for scaling up/down this shard.

This graph has three lines on it per shard, showing different aggregation intervals (hour, 10m, and 'instant'); the
larger intervals show a smoothed representation, but given Sidekiq can be *very* bursty, and the bursts are relevant, we
have the instant option as well.  Note that 'instant' actually means Grafana's auto calculated interval; when viewing
long periods of time (days) this can get large and make 'instant' approach or possible surpass the 10m interval

From the Shard Detail dashboard on any graph that shows job-specific stats, left-clicking on the line for a job opens a
menu from which the "[Worker Detail](https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail)"
dashboard can be opened.

#### Worker Detail

<https://dashboards.gitlab.net/d/sidekiq-worker-detail/sidekiq-worker-detail> is the lowest level of the
Sidekiq dashboards, and shows graphs specific to the selected worker. The graphs on this page are fairly
self-explanatory. One neat feature is that it shows which shard this job is running on in the brightly colored boxes at
the top (Queue Attribute: Shard), which can be a lot quicker than trying to find the job in the all_workers.yml file in
the gitlab code base.

#### Marginalia sampler dashboard

Spikes in Sidekiq workers worker volume could potentially saturate the pgbouncer connection pools and affect Sidekiq queueing and execution apdex.
This could happen for reasons such as:

1. Lock contention between multiple workers
1. Non-performant queries

The marginalia sampler dashboard is useful in detecting such offending workers by examining [active-counts](https://dashboards.gitlab.net/d/patroni-marginalia-sampler/patroni3a-marginalia-sampler?orgId=1&from=now-3h&to=now&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-fqdn=All&var-application=sidekiq&var-endpoint=All&var-state=active&var-wait_event_type=All&var-type=patroni) and [idle-in-transaction counts](https://dashboards.gitlab.net/d/patroni-marginalia-sampler/patroni3a-marginalia-sampler?orgId=1&from=now-3h&to=now&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-fqdn=All&var-application=sidekiq&var-endpoint=All&var-state=idle%20in%20transaction&var-wait_event_type=All&var-type=patroni).

### Logs

The Sidekiq logs have a wealth of additional metadata. In Kibana, change to the `pubsub-sidekiq-inf-gprd\*` index.
Interesting fields to search or aggregate on:

1. queue: The lower-snake-case queue name
1. jid: An ID that is the unique to a job (allocated when the job is enqueued). Useful for tracking a job through the system
1. job_status: `start`, `fail`, `deduplicated`, `done`, `deferred`, `dropped` (or empty for some ancillary cases)
   * In a debugging/incident, you *probably* want to filter for `done` so you get the timing information below.
1. meta.user: The user that caused this job to happen, if known
1. meta.root_namespace: The gitlab namespace (top level group) that the job is executing for
1. meta.project: The project that the job is executing for/on
1. meta.caller_id: what *initiated* the job. Could be a Rails controller (web or API), another Sidekiq job, and so on.
   * The "meta" fields are particularly useful when trying to find who is dumping a bunch of jobs on us and causing things to page
   * meta.root_caller_id is the user-facing request at the start of the chain, and meta.feature_category the owning stage group's category
1. scheduling_latency_s and target_scheduling_latency_s: how long the job waited in the queue, and the urgency's target
   * The [customer impact dashboard](https://log.gprd.gitlab.net/app/dashboards#/view/90dd1ec6-3f91-44f2-b768-18298e25b8af) aggregates these by namespace, worker, caller and feature category; see [sidekiq-queueing-apdex.md](sidekiq-queueing-apdex.md#customer-impact)
1. {db_,cpu_,gitaly_,redis_,}duration_s: How long the job spent in each of those areas
   * Useful for guiding investigations into slow jobs; only logged on `done` job_status (for hopefully obvious reasons)
1. exception.{class,message,backtrace}:
   * Mostly on 'fail' job_status, which is useful for debugging high error rates. You'll see lots of external calls failing (webhooks, mailers, etc) here, under normal circumstances
1. retry/retry_count:
   * See [Retries + Fails](#retries-and-fails) below

There are a bunch of other fields too, so go exploring, but the above are a really good starting point.

## A few other things

### Memory killer

Gitlab also has two possible "excessive memory usage" killers, both optional.  One is implemented as middleware[^1];
after every job runs it checks the current RSS of the single Sidekiq worker, and if that is above a configurable limit,
terminates (SIGTERM) the process.  The Daemon implementation has a separate thread that periodically checks the process
memory usage rather than at the end of any job.  It has a configurable soft limit that can be exceeded for a *short*
period before it will self-terminate, and the simple hard limit which forces an immediate termination.  At this writing,
our VM deployments use the legacy middleware implementation (although it has been mooted to move to the daemon implementation),
and our Kubernetes deployments use neither, relying instead on the kubernetes memory limits.

In either case, when a sidekiq process is killed sidekiq-cluster sees this as a 'failure', and restarts itself (and
all its other workers) entirely as a result. This is a safety-valve for run-away jobs eating all the RAM, but obviously
needs careful tuning; we don't want to rely on this under normal circumstances.

### Retries and Fails

These can be a little counter-intuitive in implementation. The `retry` field in the logs indicates
how many retries are *allowed* for this job; it will be the same for every log entry for a given job id. The
`retry_count` field records how many times the job has actually been retried, but:

1. On logs for the first attempt it will be missing (not logged)
1. Assuming the job keeps failing, on the second attempt it will log "0" (even on the job_status=="fail" log entry for the second attempt), on the third attempt it will log "1", and so on.

When a job fails with the retry_count at `retry-1`, the job will cease to be retried and possibly placed in the Dead Set
(this can be disabled per-job)

The Dead Set is a set in Redis that records any jobs that completely failed all their allowed retries; it is capped at
10K entries (or 6 months), but in practice we experience sufficient failure-rate (either unexpected, or reasonably due
to 3rd parties) that this set basically always has 9999 items in it. Do not be alarmed.

See <https://github.com/sidekiq/sidekiq/wiki/Error-Handling> for a bit of additional discussion. In particular, you may
wish to note the discussion on the *exponential + randomized backoff* of the retries. What may not be obvious however
is that the Retry (and Dead) sets are a single Redis ZSET (an ordered set). The order is a unix epoch timestamp, which
affords some efficiencies for Sidekiq polling. The downside is that all Sidekiq workers have a thread polling this set
periodically and sort of randomly (see <https://github.com/sidekiq/sidekiq/blob/main/lib/sidekiq/scheduled.rb>) so if
this set gets large it could cause some noticeable load on Redis. Thankfully in practice it stays fairly small. The
Dead Set can be inspected and jobs retried if necessary. See [Dead Set inspection](#dead-set-inspection) for more
details.

Most of our jobs have a default retry of 3, defined in <https://gitlab.com/gitlab-org/gitlab/-/blob/v13.1.0-ee/config/initializers_before_autoloader/002_sidekiq.rb#L15-16>
You can see jobs with non-default settings by searching `app/workers` and `ee/app/workers` in the gitlab codebase for
`sidekiq_options retry:`

Further, the [reliable fetcher](https://gitlab.com/gitlab-org/sidekiq-reliable-fetch) keeps a list of jobs (in redis)
that are running, and periodically (once an hour by default) looks for any jobs for which the worker heartbeat has
stopped, and if so, re-queues the jobs.  Critically, the cleanup job can and does run on *any* sidekiq node (whichever
one manages to pick up the next lease on the locking key when the previous lease expires), as it's just looking
at lists in redis.  So if you're looking for logs of the "Push", make sure you don't limit your search to a given
shard, VM, or pod

### Restarts

When Sidekiq is gracefully stopped (e.g. you request sidekiq-cluster to stop or restart and it signals all
workers to stop, or if you SIGTERM a worker directly), it gives the current job some time to finish (25s by default),
and then kills it off but pushes the job back into the Redis LIST again. As a corollary of this, jobs *really* need to
be, if not idempotent, safe in the face of being cancelled part way through and re-run later. This matters less if they
are quick and will likely finish anyway before the timeout, but long running jobs need to be carefully coded.

It's also conceivable that jobs will be run more than once, or even potentially lost (although that's lower likelihood).
See [https://gitlab.com/gitlab-org/sidekiq-reliable-fetch] for some more about that. Also as noted at
<https://github.com/sidekiq/sidekiq/wiki/Best-Practices#2-make-your-job-idempotent-and-transactional> :

```
Just remember that Sidekiq will execute your job at least once, not exactly once.
```

### Idempotence

As noted in [restarts](#restarts), it's important jobs are 'safe', but there is an additional possibility
when they are strictly Idempotent, i.e. running the same job more than once would have no additional effect.
[Sidekiq idempotent jobs](https://docs.gitlab.com/development/sidekiq/idempotent_jobs/) describes this
in detail, and may be interesting to read, as a job properly marked can be de-duplicated from the queue, reducing the
load on Sidekiq from running redundant jobs.

De-duplication is a GitLab specific feature, with one operational gotcha: it happens when the second job is being
submitted, i.e. if there is already a job in the queue, the new one is not pushed. This happens in the Sidekiq *client*
(in middleware),  which can be any Rails node (web, api, or other Sidekiq nodes). The corollary is that it is possible
to get logs with a `job_status` of `deduplicated` on a Sidekiq node for a `queue` that doesn't run on that Sidekiq
shard, which can be rather counter-intuitive. In these cases, look at `meta.caller_id`, the class name of the Sidekiq
job that attempted to schedule the job that got deduplicated. That will match up with the shard from which the log has
come.

It also means we get Sidekiq logs from web and api nodes, but that should only ever be the job_status of `deduplicated`.

#### Unblocking jobs stuck in deduplication

During Redis maintenance where master node failover occurs, the duplicate key deletion may fail and result in subsequent jobs being deduplicated during scheduling.
From logs, find the `json.idempotency_key` of the job that is stuck in deduplication by filtering for the `json.class: "CLASS_NAME"` and `json.job_status: "deduplicated"`.

On a Rails console, run the following:

```ruby
idempotency_key = <INSERT KEY FROM LOGS>
duplicate_key = "resque:gitlab:#{idempotency_key}:cookie:v2"
Gitlab::Redis::Queues.with { |c| c.del(duplicate_key) }
```

### Deferring Sidekiq jobs

In case there's an incident and the cause is runaway worker instances, you can use [Deferring Sidekiq middleware](./disabling-a-worker.md#1-using-feature-flags-via-chatops) to stop the worker from running immediately.

### Removing a slow worker from alerting

If a worker has a known performance issue that causes persistent SLO alert noise but does not need to be disabled, you can [exclude it from SLI/SLO alerting](./removing-slow-worker-from-alerting.md) while the root cause is investigated.

### Sidekiq-cron

This is an [additional gem](https://github.com/sidekiq-cron/sidekiq-cron) that allows Sidekiq jobs to be scheduled
periodically (much like Unix cron). The slightly non-intuitive detail is that the scheduler itself runs as a thread in
every Sidekiq process; for us this means many times on each VM, and once in every Kubernetes pod. The gem handles this
correctly by design, by using Redis a ZSET, and putting the jobs into Sidekiq's ScheduledSet. This does *not* affect
where the job then actually runs; that is subject to all the usual queue configuration

### Inspecting/manipulating active state

<https://docs.gitlab.com/administration/sidekiq/sidekiq_troubleshooting/#managing-sidekiq-queues> is always a starting point; our dashboards are better for inspecting (IMO), but
in the event you need to e.g. delete all the jobs in a given queue (reasons include: jobs orphaned by insufficient
migration when being removed from the app, or perhaps causing incidents), this can be a quick way to achieve that.

For more detailed inspection, you will need a Rails console. [sidekiq-inspection.md](sidekiq-inspection.md) is a good
place to start. Inspecting the 'args' attribute of the payload is also interesting, although it requires the Worker
code to interpret the meaning of the arguments. From there it's entirely possible to analyze the jobs in the queue
across various attributes (e.g. find the source of queued spam e-mails) and potentially delete them (See
<https://gitlab.com/gitlab-com/runbooks/-/snippets/1923045> for an example of that).

#### Dead Set inspection

Some starter examples.

From a Rails console:

```ruby
ds = Sidekiq::DeadSet.new
ds.each do |entry|
  job = JSON.parse(entry.value)
  puts("#{job["jid"]}: #{job["class"]} #{Time.at(job["created_at"])}")
end
```

Or if you wanted to retry certain jobs, something like this would work:

```ruby
ds = Sidekiq::DeadSet.new
ds.each do |entry|
  job = JSON.parse(entry.value)
  # Example only; pick your condition of choice to select the jobs you want to retry
  entry.retry if (job["class"] == "CreateNoteDiffFileWorker")
end
```

Retries should likely only be attempted if:

1. Any underlying reason why they have failed was temporary and has been fixed (e.g. deployed code or environment)
1. Retrying them is known to be safe/idempotent

Filtering on class name is likely a *minimum* condition, and other attributes likely need to be checked as well, e.g.
created_at and perhaps other arguments.

### Circuit breaking/throttling worker execution

When a Sidekiq worker class saturates database resources (like pgbouncer pool), it could have a domino effect such as slowing down
other worker classes execution, longer queueing time, or even taking the site down.

We have implemented a [circuit breaking feature](https://runbooks.gitlab.com/sidekiq/sidekiq-concurrency-limit/#throttlingcircuit-breaker-based-on-database-usage) to automatically identify
the offending worker, and aggressively reduce/throttle the worker's [concurrency limit](https://docs.gitlab.com/development/sidekiq/worker_attributes/#concurrency-limit)
in order to control the number of running jobs.

The circuit breaker/throttling works by checking 2 indicators:

1. Whether the worker class' `db_duration` usage (from client-side) exceeds a certain threshold.
2. Whether the worker class dominates majority of the pgbouncer connection pool.

The [Worker Concurrency Detail dashboard](https://dashboards.gitlab.net/d/sidekiq-concurrency/sidekiq3a-worker-concurrency-detail?from=now-6h&orgId=1&timezone=utc&to=now&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-worker=$__all)
has all the details of the following:

* Current concurrency limit - the current concurrency limit subjected to throttling
* Max concurrency limit - the maximum concurrency limit that all workers start from (without throttling)
* Worker concurrency - the number of concurrent running jobs
* Concurrency limit queue size - the number of deferred jobs in the concurrency limit queue
* Deferment rate - rate of jobs being deferred to the concurrency limit queue. This tells us which workers are deferred
* Throttling events - indicates whether a worker class is throttled

See [this doc](https://runbooks.gitlab.com/sidekiq/sidekiq-concurrency-limit/#throttlingcircuit-breaker-based-on-database-usage) for more details on how the circuit breaking/throttling by database usage works.

## Footnotes [^1]

[Middleware](https://github.com/sidekiq/sidekiq/wiki/Middleware) in Sidekiq is sort of a plugin
architecture that lets you inject code into the enqueuing (client-side) and processing (server-side) of jobs. We use it
heavily
