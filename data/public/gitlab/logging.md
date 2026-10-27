# HTTP Router Worker Logs

The [http-router](https://gitlab.com/gitlab-org/cells/http-router) leverages [Cloudflare Workers](https://developers.cloudflare.com/workers/) for its operations. For logs we use [Worker Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/) with a 1% head-based sampling rate and [Sentry SDK for Cloudflare](https://www.npmjs.com/package/@sentry/cloudflare) for handling all the exceptions.

## Worker Logs Overview

Worker Logs is a managed service provided by Cloudflare that handles log retention and storage while providing an intuitive interface for log consumption and analysis.

### Available Log Interfaces

Two primary interfaces are available for log analysis:

- [`Live Logs`](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/workers/services/live-logs/production-gitlab-com-cells-http-router/production): Real-time log monitoring
- [`Worker Logs`](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/workers/services/view/production-gitlab-com-cells-http-router/production/observability/logs): Historical log analysis

### Configuration Details

Log configuration is managed through the [`wrangler.toml`](https://gitlab.com/gitlab-org/cells/http-router/-/blob/c0bbfaae75be7d534713564aa29866af78705dd1/wrangler.toml#L80) configuration file.

To optimize costs while maintaining meaningful insights, we leverage head-based sampling with a [1% sampling rate](https://gitlab.com/gitlab-org/cells/http-router/-/blob/c0bbfaae75be7d534713564aa29866af78705dd1/wrangler.toml#L82) as described in the configuration file.

## Worker Sentry Integration

We leverage the [Sentry SDK for Cloudflare](https://www.npmjs.com/package/@sentry/cloudflare) to ship all exception logs to our [Sentry Instance](https://new-sentry.gitlab.net/).

We have set up the [http-router](https://new-sentry.gitlab.net/organizations/gitlab/projects/http-router/?project=39) project in Sentry. This single project hosts all environments, including `gprd` and `gstg`.
