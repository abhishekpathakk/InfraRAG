# Mixins

Mixins are a way to bundle together grafana dashboards, prometheus alerts, and rules required for a specific service or piece of software.

We have Gitab specific mixins that live in the [monitoring-mixins repo](https://gitlab.com/gitlab-com/gl-infra/monitoring-mixins/-/tree/main).

These can be configed, and genereated within or `mimir-rules` directory using a `mixin.libsonnet` configuration file.

## Example

Generating Mimir mixins.

We can create a `mixin.libsonnet` in the `mimir-rules/<tenant>/<service>/` directory.\
In this case we will use `mimir-rules/metamonitoring/mimir`, where `metamonitoring` is our mimir tenant, and `mimir` is the service we are generating the mixins for.\
First we can install the jsonnet dependency in our `mimir-rules/metamonitoring/mimir` service directory.

```bash
jb init
jb install gitlab.com/gitlab-com/gl-infra/monitoring-mixins.git/mixins/mimir@main
```

This grabs the `mimir` mixin jsonnet from the `mixins/` directory in the `gitlab.com/gitlab-com/gl-infra/monitoring-mixins.git` repository.

We can then provide any configuration overrides we want to the mixin. The configuration options can be found in the `config.libsonnet` file provided with any mixin.

```jsonnet
local mimir = import 'mimir/mixin.libsonnet';

mimir {
  _config+:: {
    product: 'Mimir',

    additionalAlertLabels: {
      team: 'observability',
      env: 'ops',
    },

    // Sets the p99 latency alert threshold for queries.
    cortex_p99_latency_threshold_seconds: 6,
  },
}
```

Finally we can run `make generate-mixins`.

This will call `mixtool` to generate the templates for us based on the provided configuration.\
If you do not have `mixtool`, install it with `gitlab.com/gitlab-com/gl-infra/monitoring-mixins.git`.\
Currently the tool does not have any package we can install via `asdf`.
