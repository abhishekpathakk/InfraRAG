# HAProxy Logging

HAProxy logs are not indexed in *Elasticsearch* due to the volume of content.
You can view logs for a single HAProxy node by connecting and tailing local logs.

```bash
# syslog
$ tail -f /var/log/haproxy.log
$ tail -n 99 /var/log/haproxy.log

# journald
$ sudo journalctl --unit haproxy.service
$ sudo journalctl --unit haproxy.service --lines 99
$ sudo journalctl --unit haproxy.service --since today
$ sudo journalctl --unit haproxy.service --grep '...'
```

This may not be ideal when trying to investigate a site-wide issue.

## Google BigQuery

HAProxy logs are collected into a table that can be queried in *BigQuery*.
This can provide the ability to search for patterns and look for recurring errors, etc.

### Finding HAProxy Logs in BigQuery

- Log into the Google Cloud web console and search or navigate to `BigQuery` in the appropriate project.
- In the `Explorer` on the left, you should open a `node` for your environment.
  This will most likely be called `gitlab-production` or `gitlab-staging`.
- You will see a `haproxy_logs` section you can expand and select the `haproxy_` table.

### Querying Logs in BigQuery

The `jsonPayload.message` field will most likely be a common item to look at since this contains the HAProxy log messages.
There are other fields to examine that may provide insights such as the `tt` field.
Here is an example query that could show `tt` values:

```sql
SELECT
  *
FROM
  `gitlab-production.haproxy_logs.haproxy_202405*`
WHERE
  jsonPayload.path LIKE '/api/v4/%'
LIMIT 1000
```

## Logging Pipeline

This is how the logging pipeline works for the `haproxy` nodes.

The `haproxy` process sends its logs to *standard output* according to the following configurations.

```plaintext
global
  log stdout len 4096 format raw daemon

defaults
  log global
  option dontlognull
```

### Syslog

The logs are then automatically collected by `journald` and sent to `/dev/log`. `/dev/log` is a Unix socket and everything that goes into it is received by the syslog daemon (`rsyslogd`).

Syslog is configured to read all configuration files in the `/etc/rsyslog.d` directory, including the configurations for the `haproxy` process.

```
$ cat /etc/rsyslog.conf

# Include all config files in /etc/rsyslog.d/
$IncludeConfig /etc/rsyslog.d/*.conf
```

```
$ cat /etc/rsyslog.d/49-haproxy.conf

# Create an additional socket in haproxy's chroot in order to allow logging via
# /dev/log to chroot'ed HAProxy processes
$AddUnixListenSocket /var/lib/haproxy/dev/log

# Send HAProxy messages to a dedicated logfile
:programname, startswith, "haproxy" {
  /var/log/haproxy.log
  stop
}
```

### Fluentd

The [gprd-base-haproxy](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/b3d6fc8f225ef7cf0144e12d47cc3868eed2c44d/roles/gprd-base-haproxy.json#L92)
Chef role includes the [gitlab_fluentd::haproxy](https://gitlab.com/gitlab-cookbooks/gitlab_fluentd/-/blob/master/recipes/haproxy.rb) recipe.
This recipe installs and configures *Fluentd* to collect and ship `haproxy` logs to *BigQuery*.

`td-agent` is a stable distribution package of Fluentd.

```
$ cat /etc/td-agent/td-agent.conf`

...
## include: modular configurations
@include conf.d/*.conf
...
```

```
$ cat /etc/td-agent/conf.d/haproxy.conf

## source: haproxy logs
<worker 0>
  <source>
    @type tail
    tag haproxy
    path /var/log/haproxy.log
    pos_file /var/log/td-agent/haproxy.log.pos
    <parse>
      @type multi_format
      ...
    </parse>
  </source>
</worker>

<filter haproxy>
  @type record_transformer
  enable_ruby
  <record>
    ...
  </record>
</filter>

## filter: hostname is not set on the haproxy logs
<filter haproxy>
  @type record_transformer
  enable_ruby
  <record>
    ...
  </record>
</filter>

<match haproxy>
  @type copy
  <store>
    @type google_cloud
    label_map {
      "tag": "tag"
    }
    buffer_chunk_limit 3m
    buffer_queue_limit 600
    flush_interval 60
    log_level info
  </store>


  @include ../prometheus-mixin.conf
</match>
```

The above output plugin (`google_cloud`) sends all the logs to Google Cloud *Stackdriver*.
You can query the logs from the Google Cloud *BigQuery*.

### Logrotate

*Logrotate* is configured to read all configuration files in the`/etc/logrotate.d` directory,
including the configurations for the `haproxy` process.

```
$ cat /etc/logrotate.conf

# Include all config files in /etc/logrotate.d/
include /etc/logrotate.d
```

```
$ cat /etc/logrotate.d/haproxy

# https://gitlab.com/gitlab-cookbooks/gitlab-haproxy/-/blob/master/files/default/logrotate-haproxy
/var/log/haproxy.log {
  hourly
  rotate 6
  missingok
  notifempty
  compress
  copytruncate
}

$ cat /etc/logrotate.d/haproxy.dpkg-dist

/var/log/haproxy.log {
  daily
  rotate 7
  missingok
  notifempty
  compress
  delaycompress
  postrotate
    [ ! -x /usr/lib/rsyslog/rsyslog-rotate ] || /usr/lib/rsyslog/rsyslog-rotate
  endscript
}
```
