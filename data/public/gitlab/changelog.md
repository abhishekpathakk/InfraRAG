# Changelog

## 2025-11-14

* **Changed:**

  * Pasting GitLab issues into the Slack channel no longer automatically adds the issue as a follow-up. You can add an existing GitLab issue as a follow-up by going to the web interface for an incident, clicking "Add follow-up", going to the "import" tab, and pasting the GitLab issue URL there.

## 2025-09-16

* **Added:**

  * New workflow for `Enterprise Application` incidents the Incident Commander is now automatically assigned an action to provide an update when incident severity is downgraded, issue [here](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/27607)
  * Updated lifecycle for `Enterprise Application` incidents to optionally ask for a RootCauseAnalysis ( RCA ), issue [here](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/27607)

## 2025-09-04

* **Changed:**

  * We've enabled the incident.io "Teams" feature using Slack groups. This may change your default filter to only show incidents for  the team you're assigned to. You can set your default filter in the [incident.io app preferences](https://app.incident.io/gitlab/user-preferences/my-dashboard). This change does not affect what incidents you can interact with.

## 2025-09-03

* **Changed:**

  * Triage incidents for GitLab.com will no longer auto-decline when the alert clears. This ensures we perform proper follow-up for auto-resolving alerts ([read more](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/27460#note_2727642821)).

## 2025-08-20

* **Changed:**

  * CMOCs will no longer be paged automatically ([read more](https://gitlab.com/gitlab-com/Product/-/issues/14269)) , to escalate please use the `1 Click Page CMOC` button on the incident slack channel or alternatively via `/inc escalate`

## 2025-08-18

* **Changed:**

  * DBO tier2 escalations are moving from PagerDuty to incident.io. Process for paging remains the same: `/inc escalate`. Paging via `/pd` will remain available for one more week.

## 2025-08-13

* **Changed:**

  * Follow-up issues in GitLab will now be [automatically assigned](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/27065) to either the "owner" or "creator" if the Owner isn't set or doesn't have a linked GitLab account. Formerly they were assigned only to the "Owner" and no one if the owner was not set.

## 2025-07-14

* **Changed:**

  * Modified S1 incidents to be [private by default](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/27029) through dynamic configuration of the "Keep GitLab issue Confidential" custom field

* **Added:**
  * Introduced new ["merged" incident status label](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26995) to better track incident lifecycle states
  * Added [automated linking of follow-ups to incident reviews](https://gitlab.com/gitlab-com/gl-infra/woodhouse/-/merge_requests/651) through woodhouse integration

## 2025-06-30

* **Changed:**
  * The "incident review" steps have been removed from the S3/S4 GitLab.com post-incident workflow. If a post-incident review is desired for an S3/S4 incident, you can still create a post-incident review manually from the "Post-incident" tab on [incident.io](https://app.incident.io/gitlab).

## 2025-06-25

* **Changed:**
  * We have switched incident.io to use UTC by default. This will apply everywhere except their on-call product. If you see any issues please let us know in #g_networking_and_incident_management

## 2025-06-24

* **Added:**
  * Introduced **Contributing Factors** field to incident.io for categorizing root causes of incidents. This includes predefined categories such as monitoring/alerting gaps, human factors, technical issues, and an "unidentified" option for unknown factors. The field is now required during the post-incident workflow. - [MR](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/9033)
  * Automated linking of incident reviews to incident issues via incident.io workflows - [Issue](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26861)
  * Automated MR linking to incident issues through woodhouse integration, allowing merge requests to be automatically associated with incident issues - [MR](https://gitlab.com/gitlab-com/gl-infra/woodhouse/-/merge_requests/642)
  * Added a nudge to remind folks that sev3/sev4 incidents do not automatically page EOC, and provides them a 1-click button that will page EOC if needed.

## 2025-06-13

* **Changed:**
  * Modified EOC (Engineer On Call) role description to clarify they serve as the initial incident responder with escalation paths when runbooks are insufficient - [MR #13565](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/13565)
  * Refactored incident management documentation to separate roles (Incident Lead, Incident Responder, etc.) from response teams (EOC, IMOC, CMOC) for better clarity - [MR #13565](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/13565)
  * Updated incident workflow documentation to reflect current incident.io processes - [MR #13454](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/13454)
  * Enhanced pingdom monitoring to create triage incidents in incident.io for better alert visibility - [MR #8890](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/8890)
  * Modified triage-ops rules to add a 10-day delay before auto-closing incidents to prevent premature closure of active incidents - [MR #540](https://gitlab.com/gitlab-com/gl-infra/triage-ops/-/merge_requests/540)

* **Added:**
  * Introduced automated incident creation from alerts with triage channel (#incidents-dotcom-triage) for initial alert review - [Issue #26541](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26541)
  * Added automated linking between follow-up issues and incident issues via new Woodhouse integration - [MR #621](https://gitlab.com/gitlab-com/gl-infra/woodhouse/-/merge_requests/621)
  * Introduced workflow diagram for EOC responsibilities during incidents - [MR #8910](https://gitlab.com/gitlab-com/runbooks/-/merge_requests/8910)
  * Added emoji reaction feature that automatically posts incident channel messages to GitLab issues (excluding images) - [Issue #26710](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26710)
  * Documented incident lead responsibilities for managing follow-up issues within one business day - [MR #14005](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/14005)

* **Fixed:**
  * Corrected issue where incident issues were being closed while incidents remained active by adding delay to auto-close rules - [MR #540](https://gitlab.com/gitlab-com/gl-infra/triage-ops/-/merge_requests/540)
  * Updated broken links and references throughout incident management documentation - [MR #13565](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/13565)

* **Removed:**
  * Disabled automatic assignment of incident lead role in favor of deliberate assignment based on incident context - [Issue #26678](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/26678)
  * Removed requirement for participants to add role information to their Zoom display names during incidents - [MR #13565](https://gitlab.com/gitlab-com/content-sites/handbook/-/merge_requests/13565)
