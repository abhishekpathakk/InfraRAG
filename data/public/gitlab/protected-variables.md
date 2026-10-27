# CI Protected Variables

## About CI Protected Variables

### Contact Information

- **Group**: Verify:Pipeline Authoring
- **Handbook**: [Pipeline Authoring](https://handbook.gitlab.com/handbook/engineering/devops/verify/pipeline-authoring/)
- **Slack**: [#g_pipeline-authoring](https://gitlab.enterprise.slack.com/archives/C019R5JD44E)

### What are CI Protected Variables?

Protected CI/CD variables are a security feature that restricts variable availability to pipelines running on protected branches or protected tags only. They provide an additional layer of security for sensitive information such as:

- Production deployment credentials
- API tokens and keys
- Database passwords
- Cloud provider credentials
- Signing certificates

### Key Characteristics

- **Protection Scope**: Only available to pipelines on protected branches/tags
- **Configuration Levels**: Can be set at project, group, or instance level
- **Merge Request Support**: Can [optionally be exposed to merge request pipelines and merged results pipelines](https://docs.gitlab.com/ci/pipelines/merge_request_pipelines/#control-access-to-protected-variables-and-runners)
- **Security Isolation**: Prevents exposure of sensitive variables in unprotected environments

### How Protected Variables Work

When a pipeline runs:

1. GitLab checks if the ref (branch/tag) is protected
2. If protected: All variables (protected and unprotected) are available
3. If unprotected: Only unprotected variables are available
4. The filtering happens during variable collection when building the pipeline

The variable filtering logic is implemented in:

- `lib/gitlab/ci/variables/builder/instance.rb`
- `lib/gitlab/ci/variables/builder/project.rb`
- `lib/gitlab/ci/variables/builder/group.rb`

### Documentation

- [Protected CI/CD Variables](https://docs.gitlab.com/ci/variables/#protect-a-cicd-variable)
- [CI/CD Variables Overview](https://docs.gitlab.com/ci/variables/)

## Troubleshooting

### Common Issues

#### Variables Not Available in Pipeline

**Symptom**: Pipeline fails because expected variables are undefined or empty

**Possible Causes**:

1. Branch/tag is not protected, but variables are marked as protected
2. Merge request pipeline doesn't have protected variable access enabled
3. Variable environment scope doesn't match the pipeline environment

**Resolution**:

1. Check if the branch/tag is protected:
   - Navigate to Settings > Repository > Protected branches/tags
2. Verify variable protection status:
   - Navigate to Settings > CI/CD > Variables
   - Check if "Protected" checkbox is enabled
3. For merge request pipelines:
   - Ensure "Protect variable" and "Expose to merge requests" settings are aligned
4. Verify environment scope matches (e.g., `*`, `production`, `staging`)

#### Protected Variables Exposed Unexpectedly

**Symptom**: Security concern that protected variables might be exposed to unprotected refs

**Verification Steps**:

1. Check pipeline ref protection status via API:

   ```bash
   curl --header "PRIVATE-TOKEN: <token>" \
     "https://gitlab.com/api/v4/projects/:id/pipelines/:pipeline_id" | jq '.ref, .protected'
   ```

2. Review variable protection settings at all levels (project, group, instance)
3. Check for any override behavior in `.gitlab-ci.yml` that might log variables

**Expected Behavior**: Protected variables are only exposed when `pipeline.protected_ref?` returns `true`

#### Variable Precedence Issues

**Symptom**: Protected variable value not being used as expected

**Cause**: GitLab has a variable precedence order where higher priority sources override lower ones

**Resolution**:

- Review the [CI/CD variable precedence documentation](https://docs.gitlab.com/ci/variables/#cicd-variable-precedence) to understand the full precedence order
- Ensure protected variables are set at the appropriate level to override other sources

### Where to Look for Logs

There are no specific logs tracking errors related to protected variables.

#### Rails Console

For deeper investigation via the [Rails Console](https://docs.gitlab.com/administration/operations/rails_console/):

```ruby
# Check if a specific branch is protected
project = Project.find_by_full_path('group/project')
project.protected_branch?('main')

# Check variable protection status
project.variables.where(key: 'MY_VAR').first.protected?

# Check pipeline protection status
pipeline = Ci::Pipeline.find(pipeline_id)
pipeline.protected_ref?
```

#### Audit Logs

For security auditing (Premium/Ultimate tier):

- Navigate to Project > Settings > Audit Events
- Filter by "ci_variable" events
- Look for variable creation, modification, or deletion events

### Known Limitations

- **Forked Projects**: Protected variables from the parent project are not available to pipelines in forks (security feature)
- **External Pull Requests**: Protected variables are never exposed to pipelines triggered by external pull requests
- **Wildcard Environments**: Protected variables with environment scope `*` apply globally, which may be broader than intended
- **Variable Masking**: Protection and masking are independent - a protected variable isn't automatically masked in logs
- **API Access**: Protected variables can still be read via API by users with Maintainer role or higher

### Performance Considerations

- **Variable Count**: Large numbers of variables (>100) can impact pipeline initialization time
- **Variable Size**: Each variable value is limited to 10,000 characters
- **Database Impact**: Variables are encrypted in the database, adding computational overhead
- **Caching**: Variable values are cached per pipeline to avoid repeated database queries

## Monitoring and Alerts

### Key Metrics to Monitor

1. **Audit Trail**:
   - Track variable modifications via audit events
   - Monitor variable deletion events

### Relevant Dashboards

- [CI Runners Service Overview](https://dashboards.gitlab.net/d/ci-runners-main/ci-runners-overview)

Note: There is no dedicated dashboard specifically for CI/CD variables at this time. Variable-related issues would typically manifest in pipeline execution metrics.

## Escalation

### When to Escalate

Escalate to the Pipeline Authoring team when:

- Protected variables are exposed to unprotected refs
- Performance degradation related to variable processing
- Security incident involving variable exposure

### Escalation Path

Contact the Pipeline Authoring team via [#g_pipeline-authoring](https://gitlab.enterprise.slack.com/archives/C019R5JD44E) Slack channel for issues with protected variables.

### Useful Information to Provide

- Pipeline ID and project path
- Variable key (not value) experiencing issues
- Protection status of the branch/tag
- Relevant error messages or logs
- Timeline of when the issue started

## Related Documentation

- [CI/CD Variables](https://docs.gitlab.com/ci/variables/)
- [Protected Branches](https://docs.gitlab.com/user/project/repository/branches/protected/)
- [Protected Tags](https://docs.gitlab.com/user/project/protected_tags/)
- [CI/CD Security Best Practices](https://docs.gitlab.com/ci/pipeline_security/)
