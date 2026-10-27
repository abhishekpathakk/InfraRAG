# Generic package runbook

## Summary

The generic packages repository enables publishing and managing generic packages, such as release binaries, in a project’s package registry.

This feature is useful for storing and distributing artifacts that don’t fit into specific package formats like npm or Maven.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* **Project level:** `/api/v4/projects/:id/packages/generic/:package_name/:package_version/:file_name`

## Observability

* [API Dashboard](https://log.gprd.gitlab.net/app/r/s/j0Cq2)
* [API Logs](https://log.gprd.gitlab.net/app/r/s/cXECj)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/generic_packages/#troubleshooting)
* [Valid package names](https://docs.gitlab.com/user/packages/generic_packages/#valid-package-filename-format)

## Service Changes

* [Recent MR's relating to Generic Packages](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?state=merged&label_name[]=group::package%20registry&search=generic%20package&sort=created_date)

## References

* [User Guide and API documentation](https://docs.gitlab.com/user/packages/generic_packages/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/generic)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/generic)
