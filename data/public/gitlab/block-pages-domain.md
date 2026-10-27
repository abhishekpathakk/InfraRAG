# Block specific pages domains through HAproxy

GitLab Pages is not fronted by Cloudflare, so this HAProxy-based blocking is the right tool for blocking abusive `*.gitlab.io` (or custom) Pages domains. For blocking traffic on any service that **is** behind Cloudflare, see the [Cloudflare blocking and managing traffic runbook](../cloudflare/managing-traffic.md#when-to-block-and-how-to-block) — Cloudflare is the **preferred first option for blocking HTTP/S traffic** elsewhere.

If the pages service is saturated you can view which
[pages domain is getting the most traffic](https://log.gprd.gitlab.net/app/dashboards#/view/8a1a3c40-7bf2-11ec-a649-b7cbb8e4f62e)
and place a block for that domain through HAproxy.

## See what domains are currently blocked

- Add the domain as a new line in
[deny-403-pages-domains.lst](https://gitlab.com/gitlab-com/security-tools/front-end-security/-/blob/master/deny-403-pages-domains.lst).
- Refresh [mirror on ops](https://ops.gitlab.net/infrastructure/lib/front-end-security/-/settings/repository)
  by opening the section mirroring repositories and click on the refresh button.
- Run chef client on pages front end nodes with: `knife ssh -C 2 "roles:gprd-base-lb-pages" "sudo chef-client"`
- You can verify that the configuration is applied by checking `/etc/haproxy/front-end-security/deny-403-pages-domains.lst` on a haproxy node.

You can observe the [rate at which haproxy denies front end requests in thanos](https://thanos.gitlab.net/graph?g0.expr=rate(haproxy_frontend_requests_denied_total%7Benv%3D%22gprd%22%2C%20type%3D%22pages%22%7D%5B5m%5D)&g0.tab=0&g0.stacked=0&g0.range_input=2d&g0.max_source_resolution=0s&g0.deduplicate=1&g0.partial_response=0&g0.store_matches=%5B%5D).

You can also block [individual IPs or apply net blocks](../frontend/ban-netblocks-on-haproxy.md#blocking-individual-ips-and-net-blocks-on-ha-proxy).
