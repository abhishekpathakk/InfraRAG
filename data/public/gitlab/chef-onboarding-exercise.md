# Chef Cookbook Onboarding: Using the Playground Cookbook

This guide walks you through the end-to-end Chef cookbook workflow using the
[chef-playground](https://gitlab.com/gitlab-cookbooks/chef-playground) cookbook — purpose-built to get hands-on experience with the Chef process before working on real cookbooks.

> **Warning:** The `chef-playground` cookbook is for learning only. It is included **only** in
> the `pre` console server role ([pre-base-console-node](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/pre-base-console-node.json))
> and ideally must never be added to any other role or environment.

## Prerequisites

- Access to [gitlab-cookbooks/chef-playground](https://gitlab.com/gitlab-cookbooks/chef-playground)
- Access to [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/)
- Knife configured locally — see [manage-chef.md](manage-chef.md)
- SSH access to the `pre` console server
- Ruby and Bundler installed locally

## Step 1 — Clone and set up the cookbook

Clone the playground cookbook:

```bash
git clone git@gitlab.com:gitlab-cookbooks/chef-playground.git
cd chef-playground
```

Install gem dependencies:

```bash
make gems
```

Run lint and unit tests to confirm everything passes before making changes:

```bash
make lint
make rspec
```

## Step 2 — Make a change

Create a new branch:

```bash
git checkout -b onboarding-<your-name>
```

Edit `recipes/onboarding-test.rb` and personalize the file content — for example, add your name or a message:

```ruby
file '/tmp/onboarding-test.txt' do
  content "Chef was here - <your-name>\n"
end
```

The recipe already includes an environment guard that ensures it only runs in `pre`:

```ruby
if node.environment == 'pre'
  # ...
end
```

This means even if the cookbook were ever converged outside `pre`, this recipe would be a no-op.

Bump the version in `metadata.rb`:

```ruby
version '0.0.4'  # increment from the current version
```

Run the tests to verify everything still passes:

```bash
make lint
make rspec
```

## Step 3 — Open and merge the cookbook MR

Push your branch and open an MR against the `main` branch of
[chef-playground](https://gitlab.com/gitlab-cookbooks/chef-playground). Once reviewed and
merged, the ops mirror will sync and the publisher job will open the chef-repo MRs automatically.
See [chef-cookbook-process.md](chef-cookbook-process.md) for a detailed explanation of this workflow.

The publisher job will:

1. Upload the new cookbook version to the Chef/Cinc server
2. Open two MRs in [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/):
   - A **non-production MR** pinning the new version for non-prod environments
   - A **production MR** pinning the new version for production environments

## Step 4 — Merge both chef-repo MRs

Since `chef-playground` is **only included in the `pre` console server role**, it is safe to
merge both MRs — no production or staging nodes run this cookbook, so the version pin has no
effect on them.

Recommended order:

1. Merge the **non-production MR** first
2. Verify the cookbook converges correctly on the `pre` console server (see Step 5)
3. Merge the **production MR**

## Step 5 — Verify on the `pre` console server

SSH to the `pre` console server (`console-01-sv-pre.c.gitlab-pre.internal`). You can find it
via knife if needed:

```bash
knife search node "role:pre-base-console-node" -a name
```

You can trigger a manual chef-client run immediately, or wait — chef-client runs automatically every ~30 minutes:

```bash
sudo chef-client
```

Verify your change was applied:

```bash
cat /tmp/onboarding-test.txt
# Chef was here - <your-name>
```

Check the chef-client output for any errors. If the run fails, see
[debug-failed-chef-provisioning.md](debug-failed-chef-provisioning.md) and
[chef-troubleshooting.md](chef-troubleshooting.md).

## Step 6 — Rollback (if needed)

If something goes wrong, see [chef-cookbook-process.md](chef-cookbook-process.md) for rollback instructions.

## What NOT to do

- Do not add `chef-playground` to any role other than `pre-base-console-node`
- Do not remove or bypass the `node.environment == 'pre'` guard in `onboarding-test.rb`
- Do not use this cookbook as a base for real infrastructure changes

## Related Links

- [chef-playground cookbook](https://gitlab.com/gitlab-cookbooks/chef-playground)
- [chef-repo](https://gitlab.com/gitlab-com/gl-infra/chef-repo/)
- [pre-base-console-node role](https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/blob/master/roles/pre-base-console-node.json)
- [chef-cookbook-process.md](chef-cookbook-process.md)
- [manage-chef.md](manage-chef.md)
- [debug-failed-chef-provisioning.md](debug-failed-chef-provisioning.md)
- [chef-troubleshooting.md](chef-troubleshooting.md)
