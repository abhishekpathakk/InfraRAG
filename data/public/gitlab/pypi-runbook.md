# PyPI runbook

## Summary

The Python Package Index (PyPI) is the official third-party software repository for Python.

Enables publishing and sharing of Python packages in projects, groups, and organizations.

Supported clients are pip and twine.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

## Observability

* [API Dashboard](https://log.gprd.gitlab.net/app/r/s/JI0qO)
* [API Logs](https://log.gprd.gitlab.net/app/r/s/z71uS)

## Troubleshooting

Where to find the PyPI package code:

### API

* **Project level:** `/api/v4/projects/:id/packages/pypi`
* **Group level:** `/api/v4/groups/:id/-/packages/pypi`
* **Instance level:** `/api/v4/packages/pypi`

* [General troubleshooting issues](https://docs.gitlab.com/user/packages/pypi_repository/#troubleshooting)

## Service Changes

* [Recent MR's relating to PyPI](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/?state=merged&label_name[]=group::package%20registry&search=pypi&sort=created_date
)
* [Twine changelog](https://twine.readthedocs.io/en/stable/changelog.html)
* [pip changelog](https://pip.pypa.io/en/stable/news/)

## References

* [User Guide](https://docs.gitlab.com/user/packages/pypi_repository/)
* [API Documentation](https://docs.gitlab.com/api/packages/pypi/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/pypi)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/pypi)
