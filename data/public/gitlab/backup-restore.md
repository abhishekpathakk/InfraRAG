# Pulp Backup and Restore

## Overview

This runbook covers backup and restore procedures for the Pulp service. Pulp's backup strategy consists of two main components:

1. **CloudSQL Database Backups** - Automated backups of the PostgreSQL database
2. **Object Storage** - Artifacts stored in GCS buckets with built-in redundancy

## Important Notes

Note that we are not leveraging the native Pulp operator for backup and restoration.
We instead rely solely on the strategies provided by our cloud provider.
Refer to the [Pulp Operator documentation](https://pulpproject.org/pulp-operator/docs/admin/guides/backup_and_restore/00-overview/) for additional details on why we are not using the Pulp Operator for backups.

## Backup Configuration

Backups should be configured via Terraform:

- [Pulp terraform module](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp)
- [Pulp terraform env config](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/pre/pulp.tf)

## Database Restore Procedure

### Prerequisites

- Access to GCP Cloud SQL Console
- Appropriate IAM permissions for database restoration
- [Pulp CLI configured and authenticated](./README.md)
- Understanding that the application will be degraded during restore

### Restore Steps

Follow [GCP's documentation for restoring from backup](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restoring#live-restore-same).

#### 1. Document Current State (Recommended for Validation)

##### Pod Counts

Gather the Pod Counts so that we can scale down and scale back up post restoration.

```bash
kubectl get deploy -n pulp
```

Document the desired Pod counts.
Note that these Deployments do NOT use Horizontal Pod Autoscalers.

###### Database PreRestore Analysis

This depends on the scenario thus the below is only an example.
Determine how we can validate a restoration was successful.
Before restoring, document the current state for post-restore comparison:

```bash
# List current users (example verification)
pulp user list | jq '.[].username' 2>/dev/null || pulp user list

# Example output:
# "user1"
# "user2"
# "admin"

# Check system status
pulp status
```

Save this output for comparison after the restore completes.

#### 2. Scale down Pulp

Scale down the Pods as to prevent any interference while the database is being restored.

```bash
kubectl patch pulp pulp -n pulp --type='merge'
  -p='
  {"spec":{
    "api":{"replicas":0},
    "content":{"replicas":0},
    "web":{"replicas":0},
    "worker":{"replicas":0}
  }}'
```

#### 3. Perform the Restore

1. In the GCP Console, navigate to your CloudSQL instance
2. Click on "Backups" in the left sidebar
3. Select the backup you want to restore from (verify the timestamp)
4. Click "Restore"
5. Confirm the restoration

**Note**: Restoration time varies based on database size. For small databases (<1GB range), expect approximately 10 minutes. Larger databases may take significantly longer.

#### 4. Scale up Pulp

Scale up, substitute the below numbers with what was documented earlier:

```bash
kubectl patch pulp pulp -n pulp --type='merge'
  -p='
  {"spec":{
    "api":{"replicas":1},
    "content":{"replicas":1},
    "web":{"replicas":1},
    "worker":{"replicas":1}
  }}'
```

#### 5. Verify the Restore

Once the restore completes and pods are stable:

1. Wait for all pods to reach Ready state:

   ```bash
   kubectl get pods -n pulp -w
   ```

2. Verify database connectivity, using the `pulp-cli`:

   ```bash
   pulp status
   ```

3. Verify data integrity by comparing with pre-restore state (the below is example only):

   ```bash
   # Check users match the backup timestamp
   pulp user list | jq .[].username
   ```

4. Confirm the data matches the backup timestamp (data created after the backup should not exist)

### Post-Restore Actions

1. Monitor application logs for any persistent errors
2. Verify that all Pulp services are functioning correctly
3. Test critical workflows (e.g., package uploads, downloads)
4. Document the restore in an incident issue

## Object Storage Restore Procedure

GCS buckets used by Pulp benefit from GCP's built-in redundancy features. In the event of storage issues:

1. Verify bucket configuration and replication settings
2. Check [GCS availability and durability documentation](https://docs.cloud.google.com/storage/docs/availability-durability)
3. Review the Terraform configuration to identify backup bucket settings and replication configuration. If data loss is confirmed, coordinate with the infrastructure team to restore from replicated buckets.
4. Contact GCP support if data loss is suspected

## References

- [Pulp Operator Backup Documentation](https://pulpproject.org/pulp-operator/docs/admin/guides/backup_and_restore/00-overview/)
- [GCP CloudSQL Backup and Recovery](https://docs.cloud.google.com/sql/docs/postgres/backup-recovery/restoring)
- [GCS Availability and Durability](https://docs.cloud.google.com/storage/docs/availability-durability)
- [Pulp Terraform Module](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/applications/pulp)
- [Pulp Helm Chart](https://gitlab.com/gitlab-com/gl-infra/charts/-/tree/main/gitlab/pulp)
- [Pulp service in argocd/apps](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/tree/main/services/pulp)

## Related Issues

- [Disaster Recovery Testing](https://gitlab.com/gitlab-org/build/team-tasks/-/issues/61)
