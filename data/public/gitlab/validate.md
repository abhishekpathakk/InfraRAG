# Validate Instrumentor Changes within Cells Infrastructure

## Overview

When making changes to the [Instrumentor], it's important to validate these changes within the Cells Infrastructure to ensure they function properly in our `Cells Organization`.

Additionally, you may need to test your changes alongside supporting services in our Cells Organization, such as the `HTTP Router` and `Topology Service`.

> [!note]
> This process is specifically for validating that changes work within Cells Infrastructure and **does NOT** replace the review requirements for the [Instrumentor] tool itself. The sandbox and testing in CI of [Instrumentor] must still be maintained to validate changes for the Dedicated product and PubSec.

## How to create a Cell with your Instrumentor Changes

**Step 1: Create and Submit Your Changes**
Create a Merge Request (MR) with your changes to the [Instrumentor] repository.

**Step 2: Wait for Image Building**
Wait for the CI jobs to complete, which will build Instrumentor images for your branch.

**Step 3: Provision a Test Cell**
[Provision a new Cell](./provisioning.md#how-to-de-provision-a-cell) by updating the `instrumentor_version` in the `TENANT_MODEL` with your branch name.

> [!note]
> The `instrumentor_version` must use kebab case.
> Image tags in [Instrumentor] automatically transform branch names to match this format.
> Example: `no_hooks_gitaly` becomes `no-hooks-gitaly`.

**Step 4: Test Your Changes**

Validate that your changes are working as expected in the cell environment.

> [!note]
> To iterate on your Instrumentor changes, follow the [`Instrument Development Flow`](./infra-development.md#development-flow)

**Step 5: Clean Up**

Once testing is complete and you've verified everything works, [de-provision the cell](./provisioning.md#how-to-de-provision-a-cell).

[Instrumentor]: https://gitlab.com/gitlab-com/gl-infra/gitlab-dedicated/instrumentor
