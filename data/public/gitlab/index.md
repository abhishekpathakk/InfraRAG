# Spamcheck

For gitlab.com we use the external Spam Check endpoint to hook up to a system run by the Security department.

## Configuration

Configured in the `Spam and Anti-bot Protection` section of <https://gitlab.com/admin/application_settings/reporting>.  It can be turned off quickly with the `Enable Spam Check via external API endpoint` checkbox in the event it causes troubles.

Configuration of the rules in the spamcheck service itself is the responsibility of the Security department; as far as gitlab.com is concerned, it is a blackbox service that we interact with via gRPC or web calls, and on-call SREs do not need to concern themselves any further with the implementation under most normal circumstances.

## Verdicts

At this writing, Akismet is also configured, and the GitLab [code base](https://gitlab.com/gitlab-org/gitlab/-/blob/master/app/services/spam/spam_verdict_service.rb#L26) will take the most restrictive (DENY) from both services.  Therefore, an issue being considered spam might be because of Akismet *or* the Security-run service.  This configuration may also change in time; check the [current settings](https://gitlab.com/gitlab-com/gl-security/runbooks/-/blob/master/automation/spamcheck.md) to be sure.

## Logs

The main GitLab Rails code-base logs the verdict from all sources along with some metadata.  These logs can be most easily located by searching for the [`json.spamcheck` field existing](https://log.gprd.gitlab.net/goto/32d7d91299b21f8ceba48503c51d3c2c).

## Metrics/Alerts

The spamcheck side can be observed [here](https://console.cloud.google.com/monitoring/metrics-explorer?pageState=%7B%22xyChart%22:%7B%22dataSets%22:%5B%7B%22timeSeriesFilter%22:%7B%22filter%22:%22metric.type%3D%5C%22logging.googleapis.com%2Fuser%2Fspamcheck%2Fverdicts%5C%22%20resource.type%3D%5C%22k8s_container%5C%22%22,%22minAlignmentPeriod%22:%2260s%22,%22aggregations%22:%5B%7B%22perSeriesAligner%22:%22ALIGN_SUM%22,%22crossSeriesReducer%22:%22REDUCE_SUM%22,%22groupByFields%22:%5B%22metric.label.%5C%22verdict%5C%22%22%5D%7D,%7B%22crossSeriesReducer%22:%22REDUCE_NONE%22%7D%5D%7D,%22targetAxis%22:%22Y1%22,%22plotType%22:%22LINE%22%7D%5D,%22options%22:%7B%22mode%22:%22COLOR%22%7D,%22constantLines%22:%5B%5D,%22timeshiftDuration%22:%220s%22,%22y1Axis%22:%7B%22label%22:%22y1Axis%22,%22scale%22:%22LINEAR%22%7D%7D,%22isAutoRefresh%22:true,%22timeSelection%22:%7B%22timeRange%22:%221h%22%7D%7D&project=glsec-spamcheck-live)

More metrics to come to prometheus/grafana in future

## Reference

* Security documentation: <https://gitlab.com/gitlab-com/gl-security/runbooks/-/blob/master/automation/spamcheck.md>
