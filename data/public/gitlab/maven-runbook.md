# Maven packages runbook

## Summary

Enables publishing and consuming Maven packages (e.g jar, war, pom) using standard Maven tooling.

Supported clients are mvn, gradle and sbt.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* **Project level:** `/api/v4/projects/:id/packages/maven`
* **Group level:** `/api/v4/groups/:id/-/packages/maven`
* **Instance level:** `/api/v4/packages/maven`

## Observability

* [API dashboard](https://log.gprd.gitlab.net/app/dashboards#/view/5baa9918-d433-4c07-b26c-1e8c008ab4ab)
* [API Logs](https://log.gprd.gitlab.net/app/discover#/view/8c689785-29c1-4250-982c-b90aa6927535)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/maven_repository/#troubleshooting)

## Service Changes

* [Recent MR's relating to Maven](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?sort=created_date&state=merged&label_name%5B%5D=group%3A%3Apackage%20registry&label_name%5B%5D=workflow%3A%3Aproduction&search=maven&first_page_size=20)
* [mvn changelog](https://maven.apache.org/release-notes-all.html)
* [gradle changelog](https://docs.gradle.org/current/release-notes.html)
* [sbt changelog](https://github.com/sbt/sbt/releases)

## References

* [User Guide](https://docs.gitlab.com/user/packages/maven_repository/)
* [API Documentation](https://docs.gitlab.com/api/packages/maven/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/maven)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/maven)
