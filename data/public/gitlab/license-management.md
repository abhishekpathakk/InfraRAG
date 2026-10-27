# ops.gitlab.net License Management

ops.gitlab.net is a self-managed GitLab instance licensed via an **online**
(cloud-activated) subscription that is provisioned from the staging fulfillment system at
[customers.staging.gitlab.com](https://customers.staging.gitlab.com).

## Overview

- The license is an **online license**, activated against and provisioned from
  `customers.staging.gitlab.com`.
- The current subscription is labeled **`A-S00160331`** in the fulfillment dashboard.

## Prerequisites / Access

- **Fulfillment portal credentials**: a staging.gitlab.com account used to manage the
  fulfillment subscription. The credentials are stored in 1Password as
  `GitLab Staging Licensing Account for Ops` in the `Production` vault.
- **ops.gitlab.net admin access**: required to apply, renew, or update the license on the
  instance itself.

## Managing the license in the fulfillment system

1. Log into [customers.staging.gitlab.com](https://customers.staging.gitlab.com) using the
   `GitLab Staging Licensing Account for Ops` credentials from the `Production` vault in
   1Password.
2. Locate subscription **`A-S00160331`** in the fulfillment dashboard.
3. Open the subscription detail page to review its status, plan, and expiry. To renew or
   update the subscription, use the renewal action on that page (the **Renew** button /
   link on the subscription detail view). If the action is not available from the portal
   UI, the subscription can be managed via the CustomersDot admin interface — see the
   [CustomersDot overview](../customersdot/overview.md).

## Re-adding / updating the license on ops.gitlab.net

If you need to re-apply the license to ops.gitlab.net (for example after a renewal or
re-provisioning):

1. Log into [ops.gitlab.net](https://ops.gitlab.net) as an admin.
2. Retrieve the **cloud activation code** for subscription **`A-S00160331`** from
   [customers.staging.gitlab.com](https://customers.staging.gitlab.com). This is a
   separate alphanumeric token, distinct from the subscription ID — the subscription ID
   only identifies the subscription in the fulfillment portal.
3. In the **Admin Area** under **Subscription** (`/admin/subscription`), enter the cloud
   activation code to activate the license.

## Verification

- Confirm the license shows as active in the ops.gitlab.net Admin Area, with the expected
  plan and expiry date for subscription `A-S00160331`.

## Related Documentation / Support

- [CustomersDot overview](../customersdot/overview.md) — the fulfillment backend.
- [Duo Enterprise License Access (staging)](../duo/duo_license.md) — related staging
  licensing flow via `customers.staging.gitlab.com`.
- Support: `#s_fulfillment` and `#g_provision` Slack channels.
