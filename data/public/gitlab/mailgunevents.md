# Mailgun Events

During the course of troubleshooting a Mailgun related incident, you may want to review all the messages Mailgun was asked to deliver and view the responses, etc. The Mailgun web console does not provide a comprehensive analytics interface to query events in a way that is helpful. This is a process you can use to allow using BigQuery in Google Cloud to process events from Mailgun.

## Collect Events

This script can be run to collect events from the Mailgun API and log them into a JSON log file.

You will need to get a Mailgun API token, and know the events domain. The events domain for most GPRD environment mail is `mg.gitlab.com`.

```ruby
require 'mailgun' # run `gem install mailgun-ruby`
require 'csv'

# First, instantiate the SDK with your API credentials, domain, and required parameters for example.
mg_client = Mailgun::Client.new('REDCATED')
mg_events = Mailgun::Events.new(mg_client, 'mc.example.com')

start = Time.parse('2024-01-16 00:00').to_i
end_time = Time.parse('2024-01-19 11:00').to_i
result = mg_events.get({ 'begin' => start, 'end' => end_time, 'limit' => 300 })

filename = "success-attempts-#{start.to_i}.ndjson"
puts filename
output = File.open(filename, 'w')
count = 0

def flatten_keys(data, parent_key = nil, result = {})
  data.each do |key, value|
    key = key.gsub('-', '_')
    new_key = parent_key ? "#{parent_key}_#{key}" : key.to_s
    if value.is_a?(Hash)
      flatten_keys(value, new_key, result)
    else
      result[new_key] = value
    end
  end
  result
end


while result
  result.to_h['items'].each do |item|
    output.write(flatten_keys(item).to_json)
    output.write("\n")
    count += 1
  end

  puts count
  result = mg_events.next
end
```

## Add Events to BigQuery

Keep in mind that these logs need to be removed and deleted when you are done and should only be put in secured locations that are private and access limited.

1. Upload the ndjson file to a Google Cloud Bucket.
2. In BigQuery, create a new dataset. You may want to set a table age to expire data after some number of days.
3. Create a new table in that new dataset. You'll need to create the table from `Google Cloud Storage`. The file format will be JSONL. You can use the schema mentioned below. Select the google bucket as a source to import data from, and make sure that under the advanced options you select to allow unknown values.

<details>
<summary>Mailgun Events Schema</summary>

```
[
  {
    "name": "event",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "method",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "timestamp",
    "mode": "NULLABLE",
    "type": "TIMESTAMP",
    "description": null,
    "fields": []
  },
  {
    "name": "flags_is_authenticated",
    "mode": "NULLABLE",
    "type": "BOOLEAN",
    "description": null,
    "fields": []
  },
  {
    "name": "flags_is_test_mode",
    "mode": "NULLABLE",
    "type": "BOOLEAN",
    "description": null,
    "fields": []
  },
  {
    "name": "log_level",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "api_key_id",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "envelope_sender",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "envelope_targets",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "envelope_transport",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "recipient",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "originating_ip",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "id",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "recipient_domain",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "message_size",
    "mode": "NULLABLE",
    "type": "INTEGER",
    "description": null,
    "fields": []
  },
  {
    "name": "message_headers_message_id",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "message_headers_to",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "message_headers_subject",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "message_headers_from",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "storage_key",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "storage_env",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "storage_url",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_description",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_tls",
    "mode": "NULLABLE",
    "type": "BOOLEAN",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_mx_host",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_session_seconds",
    "mode": "NULLABLE",
    "type": "FLOAT",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_utf8",
    "mode": "NULLABLE",
    "type": "BOOLEAN",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_attempt_no",
    "mode": "NULLABLE",
    "type": "INTEGER",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_message",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_enhanced_code",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_certificate_verified",
    "mode": "NULLABLE",
    "type": "BOOLEAN",
    "description": null,
    "fields": []
  },
  {
    "name": "delivery_status_code",
    "mode": "NULLABLE",
    "type": "INTEGER",
    "description": null,
    "fields": []
  },
  {
    "name": "reason",
    "mode": "NULLABLE",
    "type": "STRING",
    "description": null,
    "fields": []
  }
]
```

</details>

## Some Common Queries

### View failed events

```sql
SELECT
  TIMESTAMP_SECONDS(60*60 * DIV(UNIX_SECONDS(timestamp), 60*60)) AS time_interval,
  event,
  reason,
  SUBSTR(delivery_status_message, 0, 100) AS delivery_status_message,
  delivery_status_mx_host,
  COUNT(*) AS count
FROM
  `<project>.<dataset>.<table>`
WHERE
  event = 'failed'
GROUP BY
  time_interval,
  event,
  reason,
  delivery_status_message,
  delivery_status_mx_host
ORDER BY
  time_interval ASC,
  count DESC
```

### View delivered events for a single recipient

```sql
SELECT
  recipient,
  SUBSTR(message_headers_subject, 0, 30) AS subject,
  COUNT(*) AS total_emails
FROM
  `<project>.<dataset>.<table>`
WHERE
  event = 'delivered'
  AND recipient = 'test@example.com'
GROUP BY
  subject,
  recipient
ORDER BY
  total_emails DESC
  ```
