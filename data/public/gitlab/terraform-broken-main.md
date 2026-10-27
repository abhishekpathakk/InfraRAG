# Terraform Broken Main

## Summary

In order to avoid Terraform drift, we have a daily job that checks for a Terraform plan diff.

## Action

When this alert fires, it indicates one of the following:

* A change was merged into Terraform, but wasn't applied.
  * => Review [recent pipelines](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/pipelines).
  * => When in doubt, revert unapplied MR.
  * => Apply via CI.
* A change was merged into Terraform, but was only partially applied.
  * => Review [recent events](../pd-event-logger-7760xa/events.md) and [recent Terraform MRs](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/merge_requests?scope=all&utf8=%E2%9C%93&state=all).
  * => Apply via CI.
* A change was made outside of Terraform. It is temporary and safe to squash (e.g. ssh key metadata added via `gcloud ssh`).
  * => Apply via CI to squash.
* A change was made outside of Terraform. It is expected to be temporary.
  * => Figure out who introduced it. Review [recent events](../pd-event-logger-7760xa/events.md). Get them to backport the change into Terraform.
  * => If possible, apply via CI to squash, then re-introduce via proper Terraform MR.
  * => Otherwise, use state surgery ([`terraform import`](https://developer.hashicorp.com/terraform/cli/commands/import)) to import existing resource. Introduce resource via Terraform MR. Apply via CI.
* The daily job raced against a concurrent merge + apply.
  * => Rerun daily scheduled job.

## Break glass

The legacy process for applying Terraform changes involves running `tf` locally.

This may be necessary when the plan is dirty and cannot be cleaned up via CI, or when there are strict ordering constraints.

The process generally involves the following:

```
cd config-mgmt
git checkout main
git pull

cd environments/gprd
tf init
tf plan -o out.tfplan
tf apply out.tfplan
```

In order to avoid applying bad changes, a targeted apply can be performed via:

```
tf plan -target 'resource.foo' -o out.tfplan
tf apply -target 'resource.foo' out.tfplan
```

Applying manually is discouraged for several reasons:

* We do not have centralised logs for these applies (unlike CI).
* Targeted applies can miss changes, introducing drift which accumulates over time.
* Local applies may use inconsistent or out-of-date tools or dependencies.

For these reasons, it is strongly encouraged to apply via CI, and to keep plans on the `main` branch clean.
