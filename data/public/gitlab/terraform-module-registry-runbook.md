# Terraform module registry runbook

## Summary

The Terraform Module Registry allows you to publish and share Terraform modules within your GitLab instance.

> **Note:** For general Package Registry architecture, troubleshooting, and operational procedures, see the [main Package Registry runbook](README.md).

### API

* **Project level:** `/api/v4/projects/:id/packages/terraform/modules`
* **Namespace level:** `/api/v4/packages/terraform/modules/v1/:module_namespace/`

## Observability

* [API Dashboard](https://log.gprd.gitlab.net/app/r/s/3qKXy)
* [API Logs](https://log.gprd.gitlab.net/app/r/s/EZw1i)

## Troubleshooting

### Common problems

#### Module resolution errors

**Summary**

Terraform cannot resolve module addresses due to naming constraints or version issues.

**Symptoms:**

* Error: "Invalid version constraint"
* Error: "Module not found"
* Error: "Cannot apply a version constraint to module because it has a non Registry URL"

**Steps to Diagnose:**

1. Check module naming conventions (namespace, module name, system)
1. Verify namespace doesn't contain unsupported characters (dots)
1. Check version format and constraints

**Troubleshooting:**

* Verify namespace doesn't contain dots (.) - Terraform limitation
* Module versions should follow the [semantic versioning specification.](https://semver.org/)

**Resolution:**

* Avoid dots in namespace names
* Use proper semantic versioning

**References**

* [Module resolution workflow](https://docs.gitlab.com/user/packages/terraform_module_registry/#module-resolution-workflow)

## Service Changes

* [Recent MR's relating to Terraform](https://gitlab.com/gitlab-org/gitlab/-/merge_requests?scope=all&state=merged&search=terraform&label_name%5B%5D=group%3A%3Apackage%20registry)
* [Terraform changelog](https://github.com/hashicorp/terraform/releases)

## References

* [User Guide](https://docs.gitlab.com/user/packages/terraform_module_registry/)
* [API Documentation](https://docs.gitlab.com/api/packages/terraform-modules/)
* [Models](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/models/packages/terraform_module)
* [Services](https://gitlab.com/gitlab-org/gitlab/-/tree/master/app/services/packages/terraform_module)
