# Advisory Database Unresponsive Hosts/Outdated Repositories

## Symptoms

The [Advisory Database](https://gitlab.com/gitlab-org/security-products/gemnasium-db) managed by the [Vulnerability Research Team](https://handbook.gitlab.com/handbook/engineering/development/sec/secure/vulnerability-research/) communicates with many hosts to pull down third party advisories and data. These are almost always updated every day/week. This rule triggers if we are unable to communicate or get fresh information from one of these third parties.

## Possible checks

* View the URLs and resources in the [advisory_db.toml](https://gitlab.com/gitlab-org/secure/vulnerability-research/internal/vr-observability-ops/-/blob/main/advisory_db.toml) and ensure each resource is up and available.
* Checkout each repository in git and ensure commits have been made with in the allowed timeframe (`git log '--pretty=%aD' | head -n 1`)
* Check each URL is resolvable

## Resolution

If for some reason the git repository hasn't been updated, consider changing the `must_update_within = "120h"`
toml configuration to a longer time frame.
