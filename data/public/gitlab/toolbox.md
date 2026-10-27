# Connecting to a Cell's Toolbox Pod

This guide covers how to connect to a cell's toolbox pod for debugging and troubleshooting purposes.

> [!warning]
> Connecting to a toolbox pod and making manual changes should be a last resort.
> Always prefer making changes through Infrastructure as Code (IaC) or automated processes.

## Prerequisites

Follow the [breakglass access guide] to request the appropriate level of access.

Once you have the right level of access, you should get the Kubernetes cluster credentials using the
appropriate procedure depending on the `/cloud_provider` field in the tenant model of the Cell:

1. [Kubernetes cluster access procedure for AWS]
1. [Kubernetes cluster access procedure for GCP]

## Connecting to the Toolbox Pod

### Find the Toolbox Pod

List the toolbox pods in the default namespace:

```bash
$ kubectl get pod --namespace default --selector app=toolbox

```

Example output:

```
NAME                              READY   STATUS                  RESTARTS      AGE
gitlab-toolbox-8c6bff946-8lt4v    1/1     Running                 0             5d
```

### Execute a Shell in the Toolbox Pod

Execute a bash shell in the toolbox container:

```bash
kubectl exec -it <toolbox-pod-name> --container toolbox -- bash
```

Example:

```bash
kubectl exec -it gitlab-toolbox-8c6bff946-8lt4v --container toolbox -- bash
```

You should now have a shell inside the toolbox pod:

```
git@gitlab-toolbox-8c6bff946-8lt4v:/$
```

## Common Operations

### Check Migration Status

View the status of all database migrations:

```bash
gitlab-rails db:migrate:status
```

Filter for specific migrations:

```bash
gitlab-rails db:migrate:status | grep -E '<migration_version>'
```

### Run Migrations Manually

> [!warning]
> Running migrations manually should only be done as a last resort when
> automated deployment migrations fail and you need to unblock deployments.

Use the `db-migrate` script to execute migrations in the correct order (regular migrations first,
then post-deployment migrations):

```bash
./scripts/db-migrate
```

This script will:

- Check if migrations are up-to-date
- Run regular migrations (`db:migrate`)
- Run post-deployment migrations
- Perform custom instance setup

> [!note]
> For common kubectl operations, see the [Kubernetes documentation].

## Troubleshooting

### No Toolbox Pods Found

If no toolbox pods are found, check:

1. You're in the correct namespace (default is `default`)
2. The toolbox deployment exists: `kubectl get deployments -l app=toolbox`
3. Check for any deployment issues: `kubectl describe deployment <toolbox-deployment>`

[breakglass access guide]: breakglass.md
[Kubernetes documentation]: https://kubernetes.io/docs/reference/kubectl/quick-reference/
[Kubernetes cluster access procedure for GCP]: https://gitlab.com/gitlab-com/runbooks/-/blob/b67da721ff912596a37d934f5390d1432756361a/docs/cells/breakglass.md#kubernetes-cluster-access-1
[Kubernetes cluster access procedure for AWS]: https://gitlab.com/gitlab-com/runbooks/-/blob/b67da721ff912596a37d934f5390d1432756361a/docs/cells/breakglass.md#kubernetes-cluster-access
