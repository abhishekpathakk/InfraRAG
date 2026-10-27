# Rate limits in the Admin area

This page lists the request rate limits that an administrator can set in the Admin area.
It applies to GitLab.com and GitLab Dedicated.
For the values on GitLab.com, see the [Rack Attack Rate Limits Configuration Summary](README.md#rack-attack-rate-limits-configuration-summary).

Each limit here is a Rack::Attack throttle.
Each throttle also has a LabKit rule, in the cohort that the table shows.
The cohort tells you which flag to change; see [LabKit cohort flags: levers by symptom](labkit-cohort-flags.md).

## Where to set the limits

All sections are under **Admin** > **Settings** > **Network**.
Each limit has a checkbox that turns it on, a number of requests, and a period in seconds.
A limit that is turned off does not apply, and its LabKit rule does not match.

| Section | Throttle (`matched`, `RateLimit-Name`) | Counted by | LabKit cohort | Product documentation |
| --- | --- | --- | --- | --- |
| **User and IP rate limits** | `throttle_unauthenticated_api` | IP address | 2 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **User and IP rate limits** | `throttle_unauthenticated_web` | IP address | 2 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **User and IP rate limits** | `throttle_authenticated_api` | User or token | 2 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **User and IP rate limits** | `throttle_authenticated_web` | User or token | 2 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **Dependency proxy rate limits** | `throttle_authenticated_dependency_proxy` | User or deploy token | 1 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **GitLab MCP server rate limits** | `throttle_authenticated_mcp` | User or token | 1 | [User and IP rate limits](https://docs.gitlab.com/administration/settings/user_and_ip_rate_limits/) |
| **Package registry rate limits** | `throttle_unauthenticated_packages_api` | IP address | 1 | [Package registry rate limits](https://docs.gitlab.com/rate_limits/api/package-registry/) |
| **Package registry rate limits** | `throttle_authenticated_packages_api` | User or token | 1 | [Package registry rate limits](https://docs.gitlab.com/rate_limits/api/package-registry/) |
| **Files API Rate Limits** | `throttle_unauthenticated_files_api` | IP address | 1 | [Repository files API rate limits](https://docs.gitlab.com/rate_limits/api/repository-files/) |
| **Files API Rate Limits** | `throttle_authenticated_files_api` | User or token | 1 | [Repository files API rate limits](https://docs.gitlab.com/rate_limits/api/repository-files/) |
| **Deprecated API Rate Limits** | `throttle_unauthenticated_deprecated_api` | IP address | 1 | [Deprecated API rate limits](https://docs.gitlab.com/rate_limits/api/deprecated/) |
| **Deprecated API Rate Limits** | `throttle_authenticated_deprecated_api` | User or token | 1 | [Deprecated API rate limits](https://docs.gitlab.com/rate_limits/api/deprecated/) |
| **Git HTTP rate limits** | `throttle_unauthenticated_git_http` | IP address | 3 | [Git operations rate limits](https://docs.gitlab.com/rate_limits/git/#git-http) |
| **Git HTTP rate limits** | `throttle_authenticated_git_http` | User or token | 3 | [Git operations rate limits](https://docs.gitlab.com/rate_limits/git/#git-http) |
| **Git LFS Rate Limits** | `throttle_authenticated_git_lfs` | User or token | 3 | [Git operations rate limits](https://docs.gitlab.com/rate_limits/git/#git-lfs) |
| **Protected paths** | `throttle_unauthenticated_protected_paths`, `throttle_unauthenticated_get_protected_paths` | IP address | 3 | [Protected paths](https://docs.gitlab.com/administration/settings/protected_paths/) |
| **Protected paths** | `throttle_authenticated_protected_paths_api`, `throttle_authenticated_protected_paths_web`, `throttle_authenticated_get_protected_paths_api`, `throttle_authenticated_get_protected_paths_web` | User or token | 3 | [Protected paths](https://docs.gitlab.com/administration/settings/protected_paths/) |
| **Incident Management Limits** | `throttle_incident_management_notification_web` | Project path | 1 | [Incident management rate limits](https://docs.gitlab.com/administration/settings/incident_management_rate_limits/) |

`throttle_product_analytics_collector` is also in cohort 1.
It has no section in the Admin area.

## Things to know

* **Git traffic with the Git limits turned off.**
  The Git HTTP and Git LFS limits are off by default on a self-managed or Dedicated instance.
  Git requests then do not count against those throttles.
  In GitLab 19.3 before the fix, LabKit counted them under the web throttles instead.
  CI job token Git and LFS requests have no user at that layer, so LabKit counted them per IP under `throttle_unauthenticated_web`.
  [gitlab!257711](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/257711) fixed this, with backports to 19.4 and 19.3.
  GitLab.com has the Git HTTP limits turned on, which is why GitLab.com did not show the bug.
* **A change needs no deploy.**
  The limits are application settings.
  Each process caches the settings for `application_settings_cache_seconds`, 60 seconds by default.
  So a change takes effect within about a minute.
* **LabKit and Rack::Attack read the same setting.**
  A change to a limit applies to both limiters.
  To stop only LabKit from enforcing a limit, use the cohort flags, not the setting.
* **Other limits are not in this table.**
  The Admin area also has limits that the application enforces in its own code, for example raw endpoints, issue and note creation, imports and exports, and pipeline creation.
  The LabKit cohort flags do not control them.
  See [Rate limits](https://docs.gitlab.com/rate_limits/) for the full list.

## See the current values

* In the Admin area, at the sections above.
* With the API: `GET /api/v4/application/settings` returns the `throttle_*` fields.
* On the rate-limiting detail dashboard:
  the **RackAttack throttle limits** and **RackAttack throttle period (seconds)** panels show the values for throttles that have matched a request.
  The **Labkit rate limits and periods** table shows the LabKit values per rule.
