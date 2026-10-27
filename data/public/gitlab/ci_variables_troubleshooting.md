# CI/CD Variables Troubleshooting Guide

## Contact Information

- **Group**: Verify:Pipeline Authoring
- **Handbook**: [Pipeline Authoring](https://handbook.gitlab.com/handbook/engineering/devops/verify/pipeline-authoring/)
- **Slack**: [#g_pipeline-authoring](https://gitlab.enterprise.slack.com/archives/C019R5JD44E)

## Overview

This guide helps you debug and view GitLab CI/CD variables. For detailed information on variable types, precedence, and usage, see the links below.

## Variable Types

### Environment Variables (default)

String values stored as environment variables. This is the default variable type.

- **Predefined Variables** - Built-in GitLab variables automatically available in all pipelines (e.g., `CI_COMMIT_SHA`, `CI_PROJECT_NAME`, `CI_PIPELINE_ID`, `CI_JOB_ID`, `GITLAB_USER_NAME`).
- **Custom Variables** - User-defined variables that you create to store configuration values, secrets, or dynamic data. See: [Define a CI/CD variable in the .gitlab-ci.yml file](https://docs.gitlab.com/ci/variables/#define-a-cicd-variable-in-the-gitlab-ciyml-file)

See: [CI/CD Variables Documentation](https://docs.gitlab.com/ci/variables/)

### File-Type Variables

Variable contains the path to a temporary file, with the actual content stored in that file. The variable value is the file path, not the content itself. Can be set via UI (Settings → CI/CD → Variables, select "File" type), API, or Terraform, but NOT in `.gitlab-ci.yml` files.

See: [Use file type CI/CD variables](https://docs.gitlab.com/ci/variables/#use-file-type-cicd-variables)

## Variable Properties

These are optional settings that can be applied to both environment and file-type variables:

### Protected

Variables can be flaged as protected. Only available on protected branches/tags can be protected. Set via Settings → CI/CD → Variables → Check CI/CD Variables table and see the variables with a 'protected' label.

See: [Protected CI/CD variables](https://docs.gitlab.com/ci/variables/#protect-a-cicd-variable) and [Protected Branches Documentation](https://docs.gitlab.com/user/project/repository/branches/protected/)

### Masked

Variable's visibility can be set as masked. Values hidden in job logs (shown as `[masked]`). Set via Settings → CI/CD → Variables → Check CI/CD Variables table and see the variables with a 'masked' label.

See: [Mask a CI/CD variable](https://docs.gitlab.com/ci/variables/#mask-a-cicd-variable)

## Variable Sources and Precedence

Variables can come from multiple sources. When the same variable name exists in multiple sources, precedence order determines which value is used.

See: [CI/CD variable precedence](https://docs.gitlab.com/ci/variables/#cicd-variable-precedence)

### Important Notes on Precedence

**When the same variable name exists in multiple places:**

1. **Across different source types** - Higher precedence sources override lower ones. For example, Pipeline Variables override Project Variables.

2. **Within group variables** - If the same variable exists in a parent group and its subgroups, the closest (most specific) subgroup to the project wins. For example, if `MY_VAR` is defined in both `group/` and `group/subgroup1/`, and your project is at `group/subgroup1/project`, the value from `group/subgroup1/` will be used.

**Other important notes:**

- **Source tracking limitation** - Once variables reach a job's environment, they appear as plain environment variables without any indication of their original source. GitLab does not tag or label variables with their source information, making it impossible to definitively determine where each variable came from within a pipeline job. To identify variable sources, you must manually check each location (UI settings, `.gitlab-ci.yml`, trigger parameters, etc.) and compare values.
- Avoid overriding predefined variables as it can cause unexpected pipeline behavior.

### Example of Variable Override

```yaml
# Scenario: MY_VAR defined in multiple places
# - .gitlab-ci.yml default: MY_VAR = "default"
# - Project Variables (UI): MY_VAR = "project"
# - Pipeline trigger: MY_VAR = "trigger"

# Result: MY_VAR = "trigger" (highest precedence wins)
# The values from .gitlab-ci.yml and Project Variables are ignored
```

## Viewing Variables in Command Line

You can view and debug variables in pipeline jobs using shell commands.

See: [List all variables](https://docs.gitlab.com/ci/variables/variables_troubleshooting/#list-all-variables)

## Common Issues

### Variable is Empty or Missing

Variables can be defined in multiple locations (project, group, instance, or `.gitlab-ci.yml`). Check all possible sources and verify precedence rules.

**Check where variables are defined:**

1. **Project variables**: Settings → CI/CD → Variables
2. **Group variables**: Group → Settings → CI/CD → Variables
3. **Instance variables**: Admin → Settings → CI/CD → Variables
4. **`.gitlab-ci.yml`**: Check `variables:` sections. See: [Define a CI/CD variable in the .gitlab-ci.yml file](https://docs.gitlab.com/ci/variables/#define-a-cicd-variable-in-the-gitlab-ciyml-file)

### Protected Variables Not Available

Protected variables only work on protected branches/tags.

See: [Protected CI/CD variables](https://docs.gitlab.com/ci/variables/#protect-a-cicd-variable)

### Variable Shows Incorrect Value

GitLab expands variables by default. You may need to disable expansion or check for variable conflicts.

See: [Prevent CI/CD variable expansion](https://docs.gitlab.com/ci/variables/#prevent-cicd-variable-expansion)

### File-Type Variables

File-type variables contain the path to a temporary file, not the content itself.

See: [Use file type CI/CD variables](https://docs.gitlab.com/ci/variables/#use-file-type-cicd-variables)

### Masked Variables Showing in Logs

See: [Mask a CI/CD variable](https://docs.gitlab.com/ci/variables/#mask-a-cicd-variable)

## Where to Find Variables

### Via GitLab UI

Variables can be defined at project, group, or instance level through the GitLab UI.

See: [Define a CI/CD variable in the UI](https://docs.gitlab.com/ci/variables/#define-a-cicd-variable-in-the-ui)

### Via Pipeline Job

Variables can be viewed in pipeline jobs using shell commands.

See: [List all CI/CD variables](https://docs.gitlab.com/ci/variables/variables_troubleshooting/#list-all-variables)

## Common Error Messages

### "Argument list too long"

Occurs when combined CI/CD variable length exceeds shell limits. Use file-type variables or split large variables.

See: [Argument list too long error](https://docs.gitlab.com/ci/variables/variables_troubleshooting/#argument-list-too-long-error)

### "Insufficient permissions to set pipeline variables"

Occurs in downstream pipelines when trigger job defines variables. Check trigger job configuration and user permissions.

See: [Insufficient permissions to set pipeline variables error for a downstream pipeline](https://docs.gitlab.com/ci/variables/variables_troubleshooting/#insufficient-permissions-to-set-pipeline-variables-error-for-a-downstream-pipeline)

### Variable Not Expanding in Job

Default variables won't expand in job variables with the same name. Use different variable names.

See: [CI/CD variable precedence](https://docs.gitlab.com/ci/variables/#cicd-variable-precedence)

## Debugging Checklist

When a variable is missing or wrong, check variable existence, protection settings, environment scope, precedence, and naming requirements.

See: [Troubleshoot CI/CD variables](https://docs.gitlab.com/ci/variables/variables_troubleshooting/)

## Variable Limits

GitLab enforces limits on the number and size of CI/CD variables at different levels (project, group, and instance).

For current limits and how to configure them, see:

- [CI/CD variables in GitLab Application Limits](https://docs.gitlab.com/administration/instance_limits/) - Number of variables allowed at each level
- [Define a CI/CD variable in the UI](https://docs.gitlab.com/ci/variables/#define-a-cicd-variable-in-the-ui)

## Accessing Variables via Rails Console

Variables are defined in the following models:

- **Models**:
  - `Ci::Variable` - Project-level variables
  - `Ci::GroupVariable` - Group-level variables
  - `Ci::InstanceVariable` - Instance-level variables

### Common Rails Console Commands

**List all project variables for a project:**

```ruby
project = Project.find_by_full_path('group/project-name')
project.variables
```

**List all group variables for a group:**

```ruby
group = Group.find_by_full_path('group-name')
group.variables
```

**List all instance-level variables:**

```ruby
Ci::InstanceVariable.all
```

**Find a specific variable by key:**

```ruby
project = Project.find_by_full_path('group/project-name')
project.variables.find_by(key: 'MY_VAR_NAME')
```

**Check variable attributes:**

```ruby
var = project.variables.find_by(key: 'MY_VAR_NAME')
var.value           # View the value
var.protected       # Check if protected
var.masked          # Check if masked
var.environment_scope  # Check environment scope
```

**Count variables at each level:**

```ruby
# Count project variables
project.variables.count

# Count group variables
group.variables.count

# Count instance variables
Ci::InstanceVariable.count
```

**Note:** Variable values are encrypted in the database. The Rails console will automatically decrypt them when accessed through the model methods.

## References and Sources

- [GitLab CI/CD Variables Documentation](https://docs.gitlab.com/ci/variables/) - Main reference for variable types, precedence, and usage
- [Predefined Variables Reference](https://docs.gitlab.com/ci/variables/predefined_variables/) - Complete list of built-in GitLab variables
- [GitLab Application Limits](https://docs.gitlab.com/administration/instance_limits/) - Variable limits and instance-level restrictions
