# Service-Level Monitoring

## Notes

Some notes on our Service-Level Monitoring implementation. Over time these will migrate to their own pages.

### Minimum Thresholds

Service-Level Monitoring uses a statistical approach to monitoring and alerting. As with any statistical operation, sample sizes matter. This is discussed in the [Alerting on SLOs Chapter of the SRE Workbook](https://sre.google/workbook/alerting-on-slos/#low-traffic-services-and-error-budget-alerting).

The Metrics-Catalog initially used a fixed minimum RPS rate of 1 request-per-second for SLO alerting. Any service not maintaining this RPS was excluded from SLO alerting to avoid noisy alerts.

However, our SLO Alerting implementation uses Multi-Window, Multi-Burn-Rate alerting, which evaluates burn rates across multiple windows, including 1h, 6h and 3d.

In a 3d period, a 1 RPS minimum service threshold equates to 259,200 samples, but over a 1h period, this is only 3,600 samples. A service could therefore operate just under the threshold, producing say 250,000 samples over 3d, yet still be excluded from the minimum RPS threshold.

This meant that some services which could have been monitored over longer periods with SLO alerts were being excluded even though we have sufficiently large sample sizes.

To get around this, the Metrics-Catalog has migrated over to **minimum sample size thresholds** instead. This is currently set to 3600 samples. This means that in a 1h period, 3600 samples are needed (except in the case of node SLO monitoring for Gitaly, which uses 1200 samples), over a 6h period, 3600 samples are required and over 3d, 3600 samples are required.

This means that low-traffic services can be monitored over long-window periods even if they are excluded from short window periods due to low sample services.

We have two thresholds to control this. Both thresholds are optional, but both need to be met if specified:

1. `minimumSamplesForMonitoring` – This is the number of operations needed over the whole window for an alert to be triggered.
2. `minimumOpsRateForMonitoring` – This is the absolute average ops rate needed for the window for an alert to be triggered.
