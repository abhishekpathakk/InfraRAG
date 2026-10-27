# CloudFlare Analytics Engine Queries

This document contains a collection of useful queries for the Analytics Engine datasets. These
queries help monitor and analyze the Worker operations, including request patterns, handler performance, migration status,
and client activity.

## Available Datasets

There is a dataset for each environment. Go to the dataset page to use the queries in the next section.

| Dataset               | Description                                                   |
|-----------------------|---------------------------------------------------------------|
| `packages_router_ops` | Production instance, with Pulp running on the Ops environment |
| `packages_router_pre` | Testing instance, with Pulp running on the Pre environment    |

[Query page URL](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/workers/analytics-engine/studio)

## Field Definitions

The dataset uses the following structure ([source code](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp/-/blob/1b9151b21aec08c703d39b6483b087a88168b374/path-transformer-worker/worker.js#L698-716)):

- **index1**: Handler name (e.g., PoolNoOsHandler, PoolCorrectedHandler, PoolWithOsHandler)
  - These handler names may change following our need in redirecting rules. For the most up-to-date list, please
    check the [worker's latest code version](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp/-/blob/main/path-transformer-worker/worker.js).
- **blob1**: Repository path
- **blob2**: Full request path
- **blob3**: Transformed path after migration
- **blob4**: Client identifier (IP address + ID)
- **blob5**: User agent
- **double1**: Timestamp
- **double2**: Migration status (1 = migrated, 0 = not migrated)

## Query Collection

### Search for a Specific Request Path (Last 1 Hour)

```sql
SELECT
  index1 as handler_name,
  blob1 as repo_path,
  blob2 as path,
  blob3 as final_path,
  blob4 as client_identifier,
  blob5 as user_agent,
  double1 as event_timestamp,
  double2 as migrated,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
  AND blob2 LIKE '%/gitlab/gitlab-ee/ubuntu%'
GROUP BY handler_name, repo_path, path, final_path, client_identifier, user_agent, event_timestamp, migrated
ORDER BY event_timestamp DESC
```

### Count Requests by Repository Path (Last 1 Hour, Grouped by Handlers)

```sql
SELECT
  index1 as handler_name,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
  AND blob1 = '/gitlab/gitlab-ee'
GROUP BY handler_name
ORDER BY request_count DESC
```

### Count Migrated vs Not Migrated Requests (Last 1 Hour)

```sql
SELECT
  double2 as migrated,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
GROUP BY migrated
ORDER BY request_count DESC
```

### Count Requests 24 Hours Ago (1 Hour Window, Grouped by Handlers)

```sql
SELECT
  index1 as handler_name,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '25' HOUR
  AND timestamp <= NOW() - INTERVAL '24' HOUR
GROUP BY handler_name
ORDER BY request_count DESC
```

### Count All Requests (Last 1 Hour)

```sql
SELECT
  SUM(_sample_interval) as total_request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
```

### Count Requests from a Specific IP (Last 1 Hour)

```sql
SELECT
  blob4 as client_identifier,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
  AND blob4 LIKE '192.168.1.1%'
GROUP BY client_identifier
ORDER BY request_count DESC
```

### Sum Total Count by Repository Path (Last 24 Hours)

```sql
SELECT
  blob1 as repo_path,
  SUM(_sample_interval) as total_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '24' HOUR
GROUP BY repo_path
ORDER BY total_count DESC
```

### Match Specific Handlers with .deb Files (Last 24 Hours)

```sql
SELECT
  index1 as handler_name,
  blob1 as repo_path,
  blob3,
  SUM(_sample_interval) as total_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '24' HOUR
  AND index1 IN ('PoolNoOsHandler', 'PoolCorrectedHandler', 'PoolWithOsHandler')
  AND blob3 LIKE '%deb'
GROUP BY handler_name, repo_path, blob3
ORDER BY total_count DESC
```

### All Client IPs and Request Counts (Last 1 Hour)

```sql
SELECT
  blob4 as client_identifier,
  SUM(_sample_interval) as request_count
FROM packages_router_ops
WHERE
  timestamp > NOW() - INTERVAL '1' HOUR
GROUP BY client_identifier
ORDER BY request_count DESC
```

## Notes

- Replace placeholder values (like `/your/specific/path`, `gitlab-ee`, `192.168.1.1`) with actual values
- Adjust time intervals as needed (e.g., `INTERVAL '1' HOUR`, `INTERVAL '24' HOUR`)
- The `_sample_interval` field represents the count of requests
- Use `LIKE` with `%` wildcard for pattern matching on string fields
