# NuGet runbook

## Summary

NuGet is the package manager for .NET.

Supported clients are .NET CLI, NuGet CLI, and Visual Studio.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* **Project level:** `/api/v4/projects/:id/packages/nuget`
* **Group level:** `/api/v4/groups/:id/-/packages/nuget`

## Observability

* [API Dashboard](https://log.gprd.gitlab.net/app/r/s/ebMMQ)
* [API Logs](https://log.gprd.gitlab.net/app/r/s/RQtSS)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/nuget_repository/#troubleshooting)

## Service Changes

* [Recent MR's relating to NuGet](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?state=merged&label_name[]=group::package%20registry&search=nuget&sort=created_date)
* [NuGet changelog](https://learn.microsoft.com/en-us/nuget/release-notes/)

## References

* [User Guide](https://docs.gitlab.com/user/packages/nuget_repository/)
* [API Documentation](https://docs.gitlab.com/api/packages/nuget/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/nuget)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/nuget)
