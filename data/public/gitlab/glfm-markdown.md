# GitLab Flavored Markdown (GLFM)

## Overview

[GitLab Flavored Markdown](https://docs.gitlab.com/user/markdown/) (GLFM) is the Markdown syntax used in
our text fields, and provides GitLab's extensions, such as references, emojis, color chips, etc. Various
"filters" add this functionality and are part of a "pipeline", called the Banzai pipeline.
More details can be found in the [developer guide](https://docs.gitlab.com/development/gitlab_flavored_markdown/).

## Contact info

Slack channel: [#g_planner-intelligence](https://gitlab.enterprise.slack.com/archives/C04R571QF5E)

[Handbook](https://handbook.gitlab.com/handbook/product/categories/features/#planner-intelligence)

~"group::planner intelligence" is responsible for all GLFM.

## Services used

- [Web](../web/README.md) and [API](../api/README.md) for serving rails and API requests
- [Redis](../redis-cluster-cache/README.md) for caching
- [Sidekiq](../sidekiq/README.md) for asynchronous jobs
- Postgres for database
- [Gitaly](../gitaly/README.md) for getting data from git

## Logging

### Kibana

- [Logs of failed Rails requests](https://log.gprd.gitlab.net/app/r/s/FxBza)

These logs show all failed Rails requests and jobs. They can be filtered by:

- Specific action/endpoint by `json.meta.caller_id`
- Specific job class by `json.class`
- By correlation ID by `json.correlation_id`

### Sentry

- [Markdown errors in Sentry](https://new-sentry.gitlab.net/organizations/gitlab/issues/?project=3&query=is%3Aunresolved+feature_category%3Amarkdown&referrer=issue-list&statsPeriod=7d)

### Grafana

- [Planner Intelligence group error budget details](https://dashboards.gitlab.net/d/stage-groups-detail-planner_intelligence)
- [api: render Markdown document](https://dashboards.gitlab.net/d/api-rails-controller/api3a-rails-controller?var-action=POST%20%2Fapi%2Fmarkdown&orgId=1&from=now-6h%2Fm&to=now%2Fm&timezone=utc&var-PROMETHEUS_DS=mimir-gitlab-gprd&var-environment=gprd&var-stage=main&var-controller=Grape)

## Troubleshooting

### Simple testing of GLFM syntax

The best way to test out GLFM syntax and features is by using a comment or description field
using the plain text editor. With the "Preview" tab, you'll get an accurate rendering of the Markdown.

Sometimes you just need to validate basic Markdown syntax. This can be done with the
[GitLab Flavored Markdown dingus](https://gitlab-org.gitlab.io/ruby/gems/gitlab-glfm-markdown/).

It currently only handles the Markdown syntax that the underlying parser handles, not
the filters in the Banzai pipeline. That means formatting such as bold, basic link
functionality, math syntax, etc. will render faithfully, while syntax for references,
color chips, includes, etc. will not.

### A "Rendering aborted due to complexity issues" message is being displayed

The following message might be displayed:

> Rendering aborted due to complexity issues. If this is valid Markdown, please feel free to open an issue
and attach the original Markdown to the issue.

This indicates a critical Banzai filter has timed out while processing,
such as sanitization. Something in the Markdown is causing an excessive
amount of time to be taken.

Try reducing some aspect of the Markdown. Maybe there are
a large number of links, or some other aspect. You can slowly reduce
the Markdown and try until you no longer get the message.

Make sure you open an issue and include the offending Markdown, so that
developers can look at improving the offending filters.

### Some links or other GLFM not rendering, or only rendering in the first half of the document

This indicates a non-critical Banzai filter timed out while processing, such as
converting emojis, etc. When this happens we halt that filter, and
bypass any other filters. This can leave some GLFM extensions, such as
references or emojis, unprocessed.

Sometimes it might happen intermittently. The GitLab instance could be
under heavy load and the Markdown is just complex enough to sometimes
go over the limit.

Usually there is some Markdown that is excessive. Try reducing
the Markdown in some way.

### Use the Rails console to try and recreate the problem

You can use the Rails console to test out troublesome Markdown.

For example:

```ruby
text = <<~MARKDOWN
Let's **test** some _Markdown_ :thumbsup:
MARKDOWN

Banzai.render(text, project: nil)
```

will generate

```html
<p data-sourcepos="1:1-1:41" dir="auto">Let's <strong data-sourcepos="1:7-1:14">test</strong> some <em data-sourcepos="1:21-1:30">Markdown</em> <gl-emoji title="thumbs up" data-name="thumbsup" data-unicode-version="6.0">👍</gl-emoji></p>
```

If you suspect that some type of redaction is a problem, then use `render_and_post_process` and provide
the proper project.

```ruby
text = <<~MARKDOWN
See issue #1
MARKDOWN

Banzai.render_and_post_process(text, project: Project.first)
```

### Use `debug_timing` to see which filter might be the problem

By supplying `debug_timing: true`, you can output how long each filter is taking, and
which ones might be getting completely bypassed.

```ruby
text = <<~MARKDOWN
Let's **test** some _Markdown_ :thumbsup:
MARKDOWN

Banzai.render(text, project: nil, debug_timing: true)
```

might generate something like

```ruby
...
D, [2025-10-02T11:42:56.951383 #79797] DEBUG -- : 0.000052_s (0.130896_s): ImageLinkFilter [FullPipeline]
D, [2025-10-02T11:42:56.951491 #79797] DEBUG -- : 0.000046_s (0.130942_s): ExternalLinkFilter [FullPipeline]
D, [2025-10-02T11:42:58.456697 #79797] DEBUG -- : 1.505040_s (1.635982_s): EmojiFilter [FullPipeline]
D, [2025-10-02T11:42:58.456870 #79797] DEBUG -- : 0.000064_s (1.636046_s): CustomEmojiFilter [FullPipeline]
...
```

If a line is yellow, then you're close to the timeout of the pipeline/filter. If it's red,
then a filter has timed out, or the pipeline was running for too long.

### Caching and invalidating

The Markdown is initially rendered to HTML and then cached in the database. Upon display, post-processing
is done for redaction. If you edit a field and save it, the Markdown will get re-rendered and cached.

There may be times when you need to reset the cache for an entire project or group. Procedures for this
can be found in [Invalidate Markdown Cache](https://docs.gitlab.com/administration/invalidate_markdown_cache/).
