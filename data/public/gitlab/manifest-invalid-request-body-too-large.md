# Builds failing with `MANIFEST_INVALID: manifest invalid; http: request body too large`

## Background

The GitLab Container Registry enforces a configurable limit on manifest upload payloads via the [`validation.manifests.payloadsizelimit`](https://gitlab.com/gitlab-org/container-registry/-/blob/master/docs/configuration.md#payloadsizelimit) configuration option. In production, this is set to **256KB** (configured in [`gprd.yaml.gotmpl`](https://gitlab.com/gitlab-com/gl-infra/k8s-workloads/gitlab-com/-/blob/master/releases/gitlab/values/gprd.yaml.gotmpl)).

When a manifest push exceeds this limit, the registry rejects the request with a `MANIFEST_INVALID: manifest invalid; http: request body too large` error.

CNG images are signed using cosign. Each time an image is re-signed without being rebuilt, an additional signature layer is appended to the manifest.

For images with infrequently invalidated caches, the manifest can be re-signed many times over successive pipeline runs, causing the manifest payload to gradually grow until it exceeds the payload size limit.

This issue was observed during CNG builds for the `cfssl-self-sign` image ([INC-8389](https://gitlab.com/gitlab-com/gl-infra/production/-/work_items/21537), 2026-03-12, S3). A related occurrence was also tracked in [CNG#2110](https://gitlab.com/gitlab-org/build/CNG/-/work_items/2110).

## Causes

The primary cause is **repeated cosign re-signing of cached images**. When a CNG pipeline reuses a cached image (i.e., skips the build step) but still signs it, a new signature layer is added to the manifest each time. Over many pipeline runs, the accumulated signatures push the manifest past the registry's configured payload size limit.

## Symptoms

- Container image builds fail during the push phase with the error: `MANIFEST_INVALID: manifest invalid; http: request body too large`
- The failure may be intermittent if it only affects pipelines on specific branches
- CNG autodeploy pipelines may be blocked

## Troubleshooting

1. **Identify the failing image and pipeline**: Check which image and branch triggered the failure. Note whether the pipeline is running on the default branch or a non-default branch.

1. **Check the manifest size**: The error may include the actual payload size. This confirms the manifest has exceeded the registry's configured payload size limit.

1. **Determine if the image was rebuilt or cached**: If the image was pulled from cache rather than rebuilt, the manifest may have accumulated signatures from many prior pipeline runs. Images with long-lived caches are most susceptible.

1. **Check the failing CI job logs**: The error details (including the image name and manifest size) will be visible in the CNG pipeline job output.

## Resolution

> **Note:** This is a build pipeline issue, not a Container Registry issue. The CNG project is owned by the [Delivery team](https://gitlab.com/gitlab-org/delivery) (`@gitlab-org/delivery`) and [Cloud Native Images maintainers](https://gitlab.com/gitlab-org/maintainers/cloud-native-images) (`@gitlab-org/maintainers/cloud-native-images`). Escalate to them if assistance is needed.

### For MR pipelines

Trigger a fresh pipeline with the `FORCE_IMAGE_BUILDS=true` CI variable set. This forces a full image rebuild, which produces a fresh manifest with a single signature, resetting the size.

### For release pipelines

1. Set `FORCE_IMAGE_BUILDS=true` in the CI variables for the pipeline;
1. Rebuild the affected container images;
1. Rerun the `sync-images-artifact-registry` job;
1. Execute the `sync-images-gitlab-com` job.
