# An impatient SRE's guide to deleting alerts

This memo documents an opinionated methodology for triaging and dealing with unactionable alerts and alert fatigue, with the goal of ultimately reducing the alert volume in order to improve the on-call experience.

When a useless alert comes in, and you still have the mental capacity and energy to do so, don't ignore it. The next time you get dragged out of bed on a Sunday for an expiring SSL cert in a non-production environment, it's 🔨 time.

## Methodology

1. Is it a known issue?
    - **Action:** 🤫 Silence. Point to issue tracking the fix.
    - **Reason:** The issue is likely to page the next shift. If the issue is known and no short-term mitigation could be applied, there is no value in paging them again.
    - **Example:** [An incident with an alert that was silenced](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/5832#note_718803477)
1. Does this alert highlight a slow-burn problem?
    - Common examples include SSL certs expiring, disks filling up, maintenance jobs failing. These need to be dealt with, but not right away. These are also frequently examples where automation and self-healing can improve the situation.
    - **Action:** 📎 Convert paging alert into auto-created issue.
    - **Reason:** These alerts are usually not immediately actionable. We do not want to get paged for them at the weekend. Unless we reach a critical threshold, we can deal with them 1-2 days later.
    - **Example:** [Route SSLCertExpiresSoon alert to issue tracker](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4047)
1. Is this alert unactionable, not actually pointing to a user-facing problem?
    - Common examples include cause based alerts that highlight some behaviour but aren't actually impacting availability. Error rates may be including client-side errors or rate-limited requests. Or alerting may be pointing at non-production environments, or upstream services we don't control.
    - **Action:** 🔥 Delete.
    - **Reason:** Alerts that don't point to an actual problem are worse than worthless. They make on-call a bad experience, and we should not tolerate them.
    - **Examples:**
      - [Remove grpc_code=InvalidArgument from gitaly SLO](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4033)
      - [Exclude registry.pre.gitlab.com from blackbox alerts](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4035)
      - [kas: exclude rate limited RPCs from error SLI](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/3853)
1. Is this alert too noisy?
    - Some alerts are flappy or just too sensitive. Sometimes they have too low traffic, allowing a single user to impact the overall SLO.
    - **Action:** 📊 Adjust thresholds. Exclude sensitive endpoints if needed.
    - **Reason:** Noisy alerts drain precious energy during on-call shifts, and contribute to alert fatigue. "Oh, this again? Ack and ignore".
    - **Examples:**
      - [Disable the gitaly OperationService apdex completely](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/3783)
      - [Loosen blackbox exporter time range for status.gitlab.com](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/4036)
      - [Loosen frontend sshService errorRatio SLO from 0.9999 to 0.999](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/3997)
1. Is the alert legit?
    - If the alert points towards an actual user- and SLO impacting problem in a production environment that needs immediate attention, then it's probably legit.
    - **Action:** 🚒 Actually investigate the alert, focus on mitigation first, then drive improvements via capacity planning, rate limiting, "corrective actions", and [the infradev process](https://handbook.gitlab.com/handbook/engineering/workflow/#a-guide-to-creating-effective-infradev-issues).

## Resources

- [Tackling Alert Fatigue - Caitie McCaffrey](https://vimeo.com/173704290)
- [Applying cardiac alarm management techniques to your on-call - Lindsay Holmwood](https://fractio.nl/2014/08/26/cardiac-alarms-and-ops/)
- [Want to Solve Over-Monitoring and Alert Fatigue? Create the Right Incentives! - Kishore Jalleda](https://www.usenix.org/conference/srecon17europe/program/presentation/jalleda)
