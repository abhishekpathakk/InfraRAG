# NPM runbook

## Summary

NPM is the package manager for JavaScript.

Supported clients are npm and yarn.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* **Project level:** `/api/v4/projects/:id/packages/npm`
* **Group level:** `/api/v4/groups/:id/-/packages/npm`
* **Instance level:** `/api/v4/packages/npm`

## Observability

* [API Dashboard](https://log.gprd.gitlab.net/app/r/s/YdZBq)
* [API Logs](https://log.gprd.gitlab.net/app/r/s/oOi5B)

## Troubleshooting

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/npm_registry/#troubleshooting)

## Service Changes

* [Recent MR's relating to NPM](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?state=merged&label_name[]=group::package%20registry&search=npm&sort=created_date
)
* [npm changelog](https://docs.npmjs.com/cli/v8/using-npm/changelog)
* [yarn changelog](https://yarnpkg.com/advanced/changelog)

## References

* [User Guide](https://docs.gitlab.com/user/packages/npm_registry/)
* [API Documentation](https://docs.gitlab.com/api/packages/npm/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/npm)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/npm)
