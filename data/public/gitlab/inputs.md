# CI Inputs

## About CI Inputs

### Contact Information

- **Group**: Verify:Pipeline Authoring
- **Handbook**: [Pipeline Authoring](https://handbook.gitlab.com/handbook/engineering/devops/verify/pipeline-authoring/)
- **Slack**: [#g_pipeline-authoring](https://gitlab.enterprise.slack.com/archives/C019R5JD44E)

### What are CI Inputs?

CI Inputs are typed parameters that make CI/CD configurations more flexible and reusable. They allow you to:

- Pass parameters to CI configuration files
- Validate input values with types, regex patterns, and option lists
- Set default values for optional parameters
- Support string, array, number, and boolean types

### Documentation

- [CI/CD Inputs Documentation](https://docs.gitlab.com/ci/inputs/)

## Troubleshooting

### Common Issues

So far there have been no production incidents related to CI inputs.

### Where to Look for Logs

There are no specific logs tracking errors related to CI inputs.

Errors for CI inputs are visible to users in the UI when starting a pipeline,
or in API responses when triggering a pipeline via the API.

Pipelines triggered by automation (for example, pipeline schedules or merge request pipelines) will fail if CI inputs
are invalid or missing. The pipeline will be marked as failed in the pipelines list with the input error visible in the
failure message.

### Known Limitations

- Maximum 20 inputs per pipeline
- Individual input strings limited to 1 KB
- Total input content limited to 1 MB
- Variable expansion not supported in input values

## Escalation

Contact the Pipeline Authoring team via [#g_pipeline-authoring](https://gitlab.enterprise.slack.com/archives/C019R5JD44E) for issues with CI Inputs.
