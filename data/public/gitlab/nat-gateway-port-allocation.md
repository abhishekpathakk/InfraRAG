# NAT Gateway Port Allocation

## Overview

- **What does this alert mean?** A Cloud NAT gateway is running low on available TCP/UDP source ports. Each NAT IP address provides 64,512 TCP and 64,512 UDP source ports. When these are exhausted, new outbound connections will fail.
- **What factors can contribute?** High volume of concurrent outbound connections, insufficient NAT IP addresses allocated for the region, or connection leaks in services not properly closing connections.
- **What parts of the service are affected?** All egress traffic through the affected NAT gateway. This includes outbound HTTP calls, external API requests, SMTP connections, webhook deliveries, and connections to downstream dependencies outside the VPC.
- **What action is the recipient expected to take?** Identify which gateway and project is saturated, determine whether it is a traffic spike or a connection leak, and either add more NAT IPs via Terraform or investigate the offending service.

## Services

This alert covers NAT gateways across four GCP projects:

- **gprd/gstg** (`gitlab-production`, `gitlab-staging-1`): Core GitLab infrastructure NAT gateways. Team: Production Engineering.
- **Runway** (`gitlab-runway-production`, `gitlab-runway-staging`): Cloud Run NAT gateways for Runway services. GKE NAT gateways use automatic IP allocation (AUTO NAT) and are excluded. Team: Runway.

## Metrics

- **Metric Explanation:**
  - `stackdriver_nat_gateway_router_googleapis_com_nat_allocated_ports`: Number of ports currently allocated per NAT IP, exported via the Stackdriver exporter.
  - `gcp_cloud_nat_ports_capacity_total`: Total port capacity per gateway — derived from the number of NAT IPs assigned to each gateway multiplied by 64,512. Used as the denominator in the saturation ratio.
  - `gitlab_component_saturation:ratio{component="nat_gateway_port_allocation"}`: Derived saturation ratio — allocated ports divided by total capacity per gateway, joined on `router_id`, `gateway_name`, `region`, and `project_id`. Alert labels include `gateway_name` and `project_id`.

- **Mimir Tenants:**
  - `gitlab-production` (gprd) → **Mimir - Gitlab Gprd**
  - `gitlab-staging-1` (gstg) → **Mimir - Gitlab Gstg**
  - `gitlab-runway-production`, `gitlab-runway-staging` → **Mimir - Runway**

- **Threshold Reasoning:**
  - **Soft SLO (80%):** Capacity planning warning. Tamland will raise a capacity issue when this is breached.
  - **Hard SLO (90%):** Alert fires and incident.io is notified. At this point services are at risk of connection failures.

## Alert Behavior

- **Silencing:** Only silence during planned capacity changes (e.g. adding NAT IPs via Terraform) where a brief spike is expected.
- **Expected Frequency:** Rare. If firing repeatedly, investigate connection leak or plan a NAT IP increase.

## Severities

- **Severity Assignment:** s2 (incident.io) — port exhaustion causes immediate connection failures for all egress traffic through the affected gateway.
  - **Impact:** All services making outbound connections through the affected NAT gateway.
  - **Scope:** All four GCP projects. For Runway, Cloud Run NAT gateways only — GKE NAT gateways are excluded.

- **Things to Check:**
  - Which `gateway_name` and `project_id` labels are on the firing alert?
    - `gitlab-production` or `gitlab-staging-1` → gprd/gstg gateway
    - `gitlab-runway-production` or `gitlab-runway-staging` → Runway gateway
  - Is this a sudden spike or a gradual trend?
  - Are connections being properly closed, or is there a leak?

## Verification

- **Saturation ratio by gateway:**

  ```promql
  gitlab_component_saturation:ratio{component="nat_gateway_port_allocation"}
  ```

- **Filter by project:**

  ```promql
  gitlab_component_saturation:ratio{
    component="nat_gateway_port_allocation",
    project_id="gitlab-runway-production"
  }
  ```

- **Raw allocated ports per NAT IP:**

  ```promql
  stackdriver_nat_gateway_router_googleapis_com_nat_allocated_ports
  ```

- **Total port capacity per gateway:**

  ```promql
  gcp_cloud_nat_ports_capacity_total
  ```

## Troubleshooting

1. **Identify the saturated gateway** from the alert labels (`gateway_name`, `project_id`).

2. **Check current port allocation trend (gprd/gstg only)**: [NAT Gateway Port Allocation dashboard](https://dashboards.gitlab.net/d/alerts-sat_nat_host_port_allocation) shows per-VM NAT port allocation to identify which hosts are spiking in NAT port usage.

3. **Check Stackdriver logs** for NAT allocation failures:
   - Go to [GCP Logs Explorer](https://console.cloud.google.com/logs)
   - Filter: `resource.type="nat_gateway"` and `jsonPayload.allocation_status != "OK"`

## Possible Resolutions

- **Short-term (traffic spike):** If caused by a specific service, consider rate-limiting outbound connections or restarting the offending service to release leaked connections.

- **Long-term (capacity):** Add more NAT IPs to the affected region via Terraform.

  ### gprd/gstg (`gitlab-production`, `gitlab-staging-1`)

  **For `gprd` (`gitlab-production`):**
  - Update `nat_ips_us_east1_block_1` and/or `nat_ips_us_east1_block_2` in [environments/gprd/network.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/network.tf)

  > [!note]
  > `nat_ips_us_east1_block_1` is always 16 (2^4). Total NAT IPs = IPs in `nat_ips_us_east1_block_2` + 16. Only `nat_ips_us_east1_block_2` needs to be updated in practice.

  **For `gstg` (`gitlab-staging-1`):**
  - Update `count` in the `nat_us_east1` resource in [environments/gstg/network.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/network.tf)

  ### Runway (`gitlab-runway-production`, `gitlab-runway-staging`)

  **1. runway-provisioner changes:**
  - Update `nat_ips` for the affected region in [config/networks/gcp.yml](https://gitlab.com/gitlab-com/gl-infra/platform/runway/provisioner/-/blob/main/config/networks/gcp.yml)

  > [!note]
  > `nat_ips` is the **total** number of NAT IPs, not how many to add. The default is 1, so only regions with `nat_ips > 1` will have an explicit entry.

  **2. config-mgmt changes:**
  - Update the newly added Runway NAT egress IPs in [infrastructure-ips/locals.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/infrastructure-ips/locals.tf). This will trigger plans in other environments as the list of Runway egress IPs is referenced in other places. Confirm that the changes look good and have the MR applied/merged.

## Escalation

- **When to Escalate:** If port exhaustion is confirmed and cannot be resolved within 15 minutes.
- **Escalation Path:**
  - **gprd/gstg gateways:**
    1. Check `#s_production_engineering` Slack channel.
    2. Escalate to the Production Engineering on-call.
  - **Runway gateways:**
    1. Check `#f_runway` Slack channel for known issues or ongoing incidents.
    2. Escalate to the Runway team lead.
  - For any GCP infrastructure issue, open a GCP support ticket.

- **Slack Channels:**
  - `#s_production_engineering` — Production Engineering
  - `#f_runway` — Runway team

## Related Links

- [Cloud NAT Troubleshooting](cloud-nat.md)
- [Cloud NAT documentation](https://docs.cloud.google.com/nat/docs/ports-and-addresses)
- [gprd network.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gprd/network.tf)
- [gstg network.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/gstg/network.tf)
- [Runway provisioner NAT config](https://gitlab.com/gitlab-com/gl-infra/platform/runway/provisioner/-/blob/main/config/networks/gcp.yml)
- [Runway Service Documentation](../runway/README.md)
