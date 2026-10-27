# Email-based One Time Passwords (OTP)

## Summary

Email-based OTP is a mandatory authentication feature for GitLab.com users signing in with passwords. Users receive a code via email during login and must enter it to proceed. This runbook helps SREs triage and mitigate Email OTP-related incidents.

Development docs: <https://docs.gitlab.com/development/email_one_time_passwords/>.

### Similar features

It's similar to [Two-factor authentication](https://docs.gitlab.com/user/profile/account/two_factor_authentication/) but with key differences:

- **Mandatory rollout**: All GitLab.com users signing in with passwords will be required to use Email OTP[^rollout-issue]
- **Exceptions**: Email OTP is unavailable when:
  - Group policy requires other two-factor authentication methods
  - Account uses an external identity provider
  - Account is scheduled for automatic enablement at a future date[^enable-otp]

It is also similar to
[Email OTP for account email verification](https://docs.gitlab.com/security/email_verification/),
which will lock an account and require an emailed code when potential abuse is
detected.

## Escalation

Depending on the urgency required for technical assistance, the
escalation path is:

1. Ask in [`#g_sscs_authentication`](https://gitlab.enterprise.slack.com/archives/CLM1D8QR0)
1. Page the Authentication team using Incident.io Tier 2 on call (Specifically `tier2 - Authn/Authz/Pipeline Security`)

### Known & Documented Impacts

- **Password-based API authentication blocked**: `git clone` and `docker login` will fail with `Access denied`[^access-denied] when a password is used.
- **Mandatory code entry**: Once enforcement begins, users must enter the emailed code to sign in.[^email-otp-docs]

Support has an [existing 2FA removal workflow](https://handbook.gitlab.com/handbook/support/workflows/2fa-removal/) to help users who cannot access their email.

## Troubleshooting

### Symptom: Users cannot sign in

#### Cause A: Code error in authentication flow

Look for errors in:

- `VerifiesWithEmail` (`app/controllers/concerns/verifies_with_email.rb`),
- `Users::EmailVerification::GenerateTokenService`, or
- `Users::EmailVerification::ValidateTokenService`

**Solution:**

1. Confirm the issue is Email OTP-related
2. Follow **Global temporary hold**
3. Notify `#g_sscs_authentication` for developer investigation

### Symptom: Email OTP emails not being delivered

#### Cause A: Mailgun outage

Email OTP depends on Mailgun for email delivery.

**Solution:**

1. Check the [Mailgun Service runbooks](../../mailgun/README.md)
2. If Mailgun cannot fix it, follow **Global temporary hold**

#### Cause B: User error or spam filters

The email was delivered but the user cannot find it.

**Solution:**

1. Direct user to [GitLab Support](https://support.gitlab.com/).
   Support has an
   [existing 2FA removal workflow](https://handbook.gitlab.com/handbook/support/workflows/2fa-removal/)
   to help users who cannot access their email.

### Symptom: Users cannot be created or updated

#### Cause A: Code error in user enrollment

Look for errors in:

- `Users::BuildService` (new user enrollment)
- `Users::UpdateService`, or
- `Users::EmailOtpEnrollment`

**Solution:**

1. Confirm the issue is Email OTP-related
2. If it affects existing and new users, follow **Global temporary hold**
2. If it only affects new users, follow **Disable for new users**
3. Notify `#g_sscs_authentication` for developer investigation

## Mitigation Steps

### Global temporary hold

**What:** Disable Email OTP for **all** users temporarily.
Users won't see the prompt, password-based APIs revert to allowing
password authentication, and the Email OTP preference disappears from the UI. Per-user
enrollment is untouched, so users are re-enrolled automatically as soon as the setting is re-enabled.

**When:** High/critical impact affecting many/most users, e.g. a bug in the
sign-in flow, or a Mailgun outage preventing OTP codes from being delivered.

**Approval:** Incident Manager On Call (IMOC)

**Who can execute:** Anyone with GitLab.com Admin access, or SREs with Rails
Console Write privileges

**How:**

Via the Admin UI (no Rails console needed):

1. In the upper-right corner, select **Admin**.
1. In the left sidebar, select **Settings** > **General**.
1. Expand the **Sign-in restrictions** section.
1. Clear the **Enable email-based one-time passwords** checkbox[^enable-otp-admin].
1. Select **Save changes**.

Or, engage an SRE to execute via Rails console:

```ruby
# (Optional) verify current state
Gitlab::CurrentSettings.email_otp_enabled?
# Disable
Gitlab::CurrentSettings.update!(email_otp_enabled: false)
```

Either way, notify `#g_sscs_authentication`.

**Knock-on impacts:**

- Must decide when/if to re-enable
- Credential stuffing attacks possible while disabled

**FAQ:**

*Q: Users are still being asked to enter a code?*

That may be due to an existing feature,
[email OTP for account email verification](https://docs.gitlab.com/security/email_verification/),
which is not controlled by the `email_otp_enabled` setting.

### Disable for new users

**What:** Disable Email OTP enrollment for new users users temporarily.
New users could still find their way to the User Preference and enable
Email-based OTP manually.

**When:** New users can't sign up

**Approval:** Incident Manager On Call (IMOC)

**Who can execute:** Anyone with ChatOps privileges (most developers, all SREs)

**How:**

1. Validate that `Gitlab::CurrentSettings.require_minimum_email_based_otp_for_users_with_passwords`
   is `false`.
1. In Slack, go to `#production`
1. (Optional) Verify current state: `/chatops gitlab run feature get enrol_new_users_in_email_otp`
1. Disable: `/chatops gitlab run feature set enrol_new_users_in_email_otp false`
1. Notify `#g_sscs_authentication`

**Knock-on impacts:**

- Must decide when/if to re-enable
- Must decide when/if to enforce Email OTP for users who signed up
  while `enrol_new_users_in_email_otp` was disabled.

[^rollout-issue]: <https://gitlab.com/gitlab-org/gitlab/-/issues/566615>
[^enable-otp]: <https://docs.gitlab.com/user/profile/account/two_factor_authentication/#enable-email-otp>
[^access-denied]: See [Two Factor Authentication Troubleshooting docs](https://docs.gitlab.com/user/profile/account/two_factor_authentication_troubleshooting/#error-http-basic-access-denied-if-a-password-was-provided-for-git-authentication-). Users must switch to using a Personal Access Token ([1](https://gitlab.com/gitlab-org/gitlab/-/blob/7f14ebed2fa690bfd77a2c9a507da4a12706eba2/doc/topics/git/clone.md#L63), [2](https://gitlab.com/gitlab-org/gitlab/-/blob/7f14ebed2fa690bfd77a2c9a507da4a12706eba2/doc/user/packages/container_registry/authenticate_with_container_registry.md#L43-44))
[^email-otp-docs]: <https://docs.gitlab.com/user/profile/account/two_factor_authentication/#sign-in-with-email-otp>
[^enable-otp-admin]: See [Enable email OTP](https://docs.gitlab.com/administration/settings/sign_in_restrictions/#enable-email-otp). Leave **Require email verification when account is locked** as-is when disabling for an incident — it's a separate, unrelated setting.
