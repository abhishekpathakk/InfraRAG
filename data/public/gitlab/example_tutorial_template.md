# Example Tutorial Template

## Learning objectives

* Gain a high-level view of the major components and behaviors of the service.
* Understand how requests are sent to the service via its API.  Learn which request types are synchronous versus asynchronous.
* Trace an example request through the service layers.
* Use the service dashboard to observe typical throughput, latency, and error rate for the service as a whole and its individual components and workers.
* Explore sub-populations of requests using custom filtering and aggregation of Kibana log events.
* Directly query a service node using its API.

## Background

### What does this service do?

Describe the purpose of this service.  What role does it fill?  What behaviors satisfy that goal?

To illustrate this purpose, it may help to show:

* screenshots of the service's web UI
* annotated list of the main API endpoints
* list of common use-cases or client personas
* diagram of how this service fits into the overall application architecture

### What are its main dependencies and clients?

Describe its relationship to other services it directly calls and those that call it.

## Walk-through: Life of a request

May include a components diagram showing which components directly interact.

May include a sequence diagram showing the order of events in a series of interactions.
This kind of diagram can concisely map the purpose and order of interactions with other services.
It can also visually highlight important or unintuitive portions of the request-processing behavior, such as a group of calls to helper services
being made concurrently, with the slowest responder of that group dominating the overall latency.

If it does not distract from the content, these diagrams may indicate (e.g. via label or color-code) which interactions are observable with the tools demoed in this tutorial.

## Demo: Observing a single example request

Show how to either choose a typical request from the service's event logs or manually create a synthetic request.

Show an example of a typical request and response.
If the full details (e.g. request/response bodies) would be distracting, then elide it in the demo (especially if you have a separate section for hands-on practice).

## Demo: How to interpret the dashboards representing service health, capacity, errors, and other key properties

List the key behaviors again, and map them to elements on the service dashboard.

### What does normal look like?

Record a video or screenshots showing the contemporary dashboard sections.
Showing concrete examples to accompany the narrative helps tie observable traits to the abstract behaviors described in earlier sections.

### What does abnormal look like?

Pick one or two examples of abnormal behavior that can be explained in terms of the behaviors and properties described in earlier sections.
For example, show how a surge of requests jointly affects the throughput and latency graphs and may lead to queuing on upstream callers and pressure on downstream dependencies.

Use this example to briefly describe the immediate effects (e.g. client timeouts and retries, SLO alerting, auto-scaling).
If practical, offer suggestions about how to decide whether or not a case like this warrants further investigation and what some potential remedies might be.

If we have a decent runbook for this service, cite it for additional failure modes.

## Demo: How to explore patterns and changes in the nature of requests and responses

How do we answer ad hoc questions about the service's workload and behaviors?
For some services this is easier than others, but this is always a critical topic to address.

Most services export performance metrics to efficiently answer generic questions about workload.  For this demo, focus on the next steps of investigating an anomaly, such as:

* For services that emit structured event logs (e.g. JSON formatted request logs), recent log entries are often available via Kibana, which provides convenient ad hoc filtering and aggregation.
* For long-term analysis and for unstructured event logs, raw logs are typically archived to Stackdriver and may be available for ad hoc query via BigQuery.
* When event logs do not suffice, stack profiling, dynamic tracing, or traffic sampling may lead to novel insights and inspire future enhancements to logging and instrumentation.

List what options are available for analyzing this service, and then walk through a common use-case including screenshots or recording.
Explicitly state the example questions you are showing how to answer.
Ideally make it a short progression of exploratory questions, showing how iterative analysis and assumption-testing is a crucial part of reverse engineering.
For example, suppose the service dashboard shows an increase in HTTP 500 responses.

* How do we find the associated request paths?
* Are the most common request paths for failed requests distinct from the most common request paths overall?
* Are the failures coming from a single service node?  Or a specific set of client IPs?  Do they have a distinctive user-agent string?
* Are these errors all associated with high latency, such that timeouts in this or other services may play a role?  If so, is the time spent in this service or in a dependency it calls?

## Quick reference

Briefly reiterate key concepts from the overview.

* To support returning visitors, include a quick reference section with a terse summary of steps or commands.
* Include enough context to support a user who does not have time to re-read any other section.

## Exercises

Optionally include safe non-destructive practice exercises to reinforce the concepts, techniques, and tools covered by this tutorial.
Include a range of difficulties.
Ensure the questions clearly relate to content and themes presented in this tutorial are answerable primarily with content presented in this tutorial.
Ideally also include hints or full solutions (hidden by default).

Examples:

* *Performance:*
  * What do you think would happen to this service's throughput, response latency, and error rate if...
    * One of its dependencies became 10x slower for all requests.
    * The rate of incoming requests increased by 10x.
    * 1% of incoming requests became 10x slower.
    * 50% of this service's nodes disappeared, causing the same overall request rate to be concentrated into the surviving 50% of servers.
    * 50% of client nodes disappeared, causing the same overall request rate to be concentrated into the surviving 50% of clients, such that each client sends 2x its normal request rate.
* *Observability:*
  * What is the most common request path (or rails route) handled by this service?
  * How many nodes does this service currently run in the production environment?
  * Query the service's metrics endpoint and review the list of raw metrics.  Find an example of a gauge, counter, and histogram.
    Repeat the query and see how they change over time.
  * Choose a graph on the service dashboard and review its PromQL query.  What metric is being graphed?  What labels (dimensions) does this metric provide?
    How does it relate to the raw metrics exported by the service itself? (*Note:* Answering this last part may require a separate tutorial on Prometheus recording rules.)
* *Dependencies exploration:*
  * Review the service's main configuration file.  What other services is it explicitly configured to directly interact with?
    Are there additional services it uses either implicitly or via dynamic configuration?
  * List or trace new and existing outgoing connections from a service node via TCP, UDP, or Unix socket.  Does this match the expected list of dependencies?
  * List or trace new and existing incoming connections to a service node via TCP, UDP, or Unix socket.  Does this match the expected list of clients?

## Summary

Conclude with a summary of key points that ties the presented content back to the learning objectives.
How does the presented content satisfy each of the learning objectives?
Here we can use the more concrete terms and concepts covered in the material.

The goal here is to give the reader a moment to reflect on the distance traveled and enjoy a milestone on their journey.

For the tutorial author, this is an opportunity to reflect on whether the content aligns well with the learning objectives and to refine scope if needed.

## Learn more

Annotated list of related supplemental material.  This may include resources like:

* Related GitLab tutorials (e.g. deeper dive into tools or techniques shown, related service layers, etc.)
* External documentation or tutorials on the tools and core concepts
* GitLab product documentation for the GitLab services mentioned here (docs.gitlab.com)
* Dashboards used in the demos
* Runbook sections, especially if they document additional known failure modes or additional analytical methods

Repeat links cited inline, to consolidate the list of supplemental material.

For each link, explain why the reader may be interested -- how it relates to this tutorial's topic and what additional learning objectives the supplemental work supports.
