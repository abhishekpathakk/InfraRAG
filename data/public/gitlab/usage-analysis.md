# Vault Audit Log Analysis

## Introduction to Vault Audit Logs

Vault audit logs record all requests and responses to Vault, providing a comprehensive audit trail of who accessed which secrets and when. Analyzing these logs can help with:

- Security monitoring and compliance verification
- Identifying unused secrets that could be candidates for removal
- Tracking secret rotation patterns and ensuring compliance with rotation policies
- Capacity planning based on usage patterns
- Troubleshooting authentication and access issues

## Loading Audit Logs from GCS to BigQuery

Before you can analyze Vault audit logs, you need to load them from Google Cloud Storage (GCS) into BigQuery.

### Preparing BigQuery Dataset

Ensure you have access to the `gitlab-ops.vault_audit_investigation` dataset in BigQuery. This access is typically provided to SREs, but can also be obtained through an access request.

If this dataset does not exist then you should be able to create this through the [GCP console UI](https://console.cloud.google.com/bigquery?project=gitlab-ops) ([related docs](https://docs.cloud.google.com/bigquery/docs/datasets)).

#### Schema Definition

Create a local file named `vault.json` with the following schema definition:

```json
[
  {
    "name": "time",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "The timestamp when the request was received by Vault"
  },
  {
    "name": "backend_type",
    "type": "STRING",
    "mode": "NULLABLE",
    "description": "The type of audit log entry (request, response)"
  },
  {
    "name": "auth",
    "type": "JSON",
    "mode": "NULLABLE"
  },
  {
    "name": "request",
    "type": "JSON",
    "mode": "NULLABLE"
  },
  {
    "name": "response",
    "type": "JSON",
    "mode": "NULLABLE"
  }
]
```

This schema captures the key components of Vault audit logs:

- `time`: When the request was received
- `backend_type`: Whether this is a request or response log
- `auth`: JSON object containing authentication details
- `request`: JSON object containing request details
- `response`: JSON object containing response details

### Loading Data from GCS

#### Loading a Single Day of Data

> [!note]
> When testing modified or new queries it may be beneficial to load a smaller amount of data like a day first.
> This will speed up iteration and lower costs as BigQuery charges based on the amount of data processed.

Use the following command to load a single day's worth of Vault audit logs from GCS to BigQuery:

```shell
bq load --ignore_unknown_values=true --project_id gitlab-ops --source_format NEWLINE_DELIMITED_JSON \
  vault_audit_investigation.single_day \
  'gs://gitlab-ops-logging-archive/gke/vault/dt=YYYY-MM-DD/*.gz' vault.json
```

> [!note]
> Replace `YYYY-MM-DD` with the date for which you want to analyze logs (typically the previous day).

#### Loading the Entire Retention Period

To load the entire available retention period of data, you can use the following command:

```shell
# List all date folders and format them for the bq load command
URIS=$(gsutil ls 'gs://gitlab-ops-logging-archive/gke/vault/' | sed 's/$/*.gz/' | tr '\n' ',' | sed 's/,$//')

# Load all data into BigQuery
bq load --ignore_unknown_values=true --project_id gitlab-ops --source_format NEWLINE_DELIMITED_JSON \
  vault_audit_investigation.full_retention_period \
  "${URIS}" vault.json
```

## Common Audit Log Analysis Queries

### Query 1: Secret Access Metrics by Mount Type (KV v2 Data Paths)

This query provides metrics on secret access patterns:

```sql
SELECT
  count(1) AS count,
  count(distinct json_extract_scalar(request, "$.path")) AS unique_paths,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)) AS month,
  json_extract_scalar(response, "$.mount_type") AS mount_type
FROM `gitlab-ops.vault_audit_investigation.single_day`
WHERE
  backend_type = "response" AND
  json_extract_scalar(request, "$.operation") = "read" AND
  json_extract_scalar(response, "$.mount_type") = "kv" AND
  regexp_contains(json_extract_scalar(request, "$.path"), "[^/]+/data/.+")
GROUP BY
  backend_type,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)),
  json_extract_scalar(response, "$.mount_type")
```

**Purpose**: This query shows the total number of access requests and unique secrets accessed, broken down by mount type and month.

> [!note]
> The count of unique secret paths will be lower than the actual number of active secrets when using the External Secrets Operator, as it will only sync each secret once during the secret versions lifecycle.

### Query 2: All Secret Access Metrics by Mount Type (Excluding Metadata)

This query is similar to the first one but includes all mount types while excluding metadata paths:

```sql
SELECT
  count(1) AS count,
  count(distinct json_extract_scalar(request, "$.path")) AS unique_paths,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)) AS month,
  json_extract_scalar(response, "$.mount_type") AS mount_type
FROM `gitlab-ops.vault_audit_investigation.single_day`
WHERE
  backend_type = "response" AND
  json_extract_scalar(request, "$.operation") = "read" AND
  json_extract_scalar(response, "$.mount_type") = "kv" AND
  NOT regexp_contains(json_extract_scalar(request, "$.path"), "[^/]+/metadata/.+")
GROUP BY
  backend_type,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)),
  json_extract_scalar(response, "$.mount_type")
```

**Purpose**: This query provides a broader view of secret access patterns across all mount types in Vault.

### Query 3: Secret Rotation Metrics by Mount Type

This query helps track secret rotation patterns:

```sql
SELECT
  count(1) AS count,
  count(distinct json_extract_scalar(request, "$.path")) AS unique_paths,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)) AS month,
  json_extract_scalar(response, "$.mount_type") AS mount_type
FROM `gitlab-ops.vault_audit_investigation.single_day`
WHERE
  backend_type = "response" AND
  json_extract_scalar(request, "$.operation") = "update" AND
  json_extract_scalar(response, "$.mount_type") = "kv" AND
  json_extract_scalar(response, "$.data.version") != "1" AND
  NOT regexp_contains(json_extract_scalar(request, "$.path"), "[^/]+/metadata/.+")
GROUP BY
  backend_type,
  format_timestamp("%Y-%m", date_trunc(time, MONTH)),
  json_extract_scalar(response, "$.mount_type")
```

**Purpose**: This query shows the number of secret rotations per month, excluding initial creations (version 1).

## References

- [Vault Audit Logs Documentation](https://developer.hashicorp.com/vault/docs/audit)
- [BigQuery Best Practices](https://docs.cloud.google.com/bigquery/docs/best-practices-costs)
- [External Secrets Operator Documentation](https://external-secrets.io/latest/)
