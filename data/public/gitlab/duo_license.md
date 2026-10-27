# Duo Enterprise License Access Process for Staging Environment

This guide explains how to self-service Duo Enterprise license access in the staging environment for backend developers, SREs, and other engineers who need to test AI features.

---

## Prerequisites

- Active staging.gitlab.com account, if you do not have one go to [staging](https://staging.gitlab.com/help) to sign in with your GitLab email account
- Existing Ultimate/Premium license on staging
- GitLab.org group membership

## Access Request Process for Zuora Sandbox

Before you can manage licenses in Zuora, you'll need access to the Zuora Central Sandbox environment:

1. Create an Access Request issue in the [access-requests project](https://gitlab.com/gitlab-com/team-member-epics/access-requests)
2. Request access to **[Staging] Zuora Central Sandbox (Tenant ID: 10000796)**
3. Provide a justification (e.g., "Need to test Duo Enterprise licensing")
4. Your manager will need to approve the request with proper labels

After approval, a member of the fulfillment team will provision your Zuora access.

## Self-Service Process

### Access License Management

1. Log in to [customers.staging.gitlab.com](https://customers.staging.gitlab.com) using your staging.gitlab.com credentials
2. Locate and copy your Zuora subscription ID (format: A-ABC123...)

### Add Duo License Through Zuora

1. Access Zuora through Okta SSO (Central Sandbox - Staging environment)
2. Use search bar (or CMD+K) to locate your subscription using the Zuora ID
3. Click "Create order"
4. Select "Add product"
5. Choose Duo Enterprise version
   - Click the arrow next to the product
   - Select desired renewal rate
   - Check the box to confirm selection
6. Click "Add product"
7. Click "Activate"

### Verify License Access

1. Sign into [staging.gitlab.com](https://staging.gitlab.com)
2. Navigate to any project
3. Open Web IDE or Code Suggestions feature
4. [Confirm Duo functionality is active](https://docs.gitlab.com/user/gitlab_duo/setup/#run-a-health-check-for-gitlab-duo)

## Troubleshooting

If you encounter issues, check the following:

| Symptom | Verification Steps | Resolution |
| --------- | ------------------- | ------------ |
| Features not available | Check subscription status in customers.staging.gitlab.com | Follow self-service steps above |
| Need upgrade from Duo Pro | Check current license type in subscription details | Create new order for Duo Enterprise |
| Authorization errors | Verify Okta access and permissions | Contact #g_provision |

The GitLab AI Features Health Check will surface specific errors if there are issues with:

- License validation
- Feature availability
- Access permissions

## Additional Information

- Licenses are managed at the namespace level
- The gitlab-org namespace on staging has a custom setup
- Most developers should use staging environment rather than local setup
- Duo Enterprise is preferred over Duo Pro for complete feature testing

## Related Documentation

- [AI Features Documentation](https://docs.gitlab.com/development/ai_features/)
- [Code Suggestions Setup Guide](https://docs.gitlab.com/development/ai_features/code_suggestions/)
- [License Management Guidelines for Code Suggestions](https://docs.gitlab.com/development/ai_features/code_suggestions/#setup-instructions-to-use-gdk-with-the-code-suggestions-add-on)
- [CLOUD_CONNECTOR_SELF_SIGN_TOKENS environment variable](https://docs.gitlab.com/development/ai_features/#optional-set-cloud_connector_self_sign_tokens-environment-variable)

## Support Channels

For issues with self-service process:

- Primary Support: #g_provision Slack channel
- Secondary Support: #s_fulfillment Slack channel
- Documentation Issues: [GitLab AI Documentation](https://docs.gitlab.com/development/ai_features/)

## Notes

- Keep subscription ID handy for future reference
- Automatic seat assignment is planned for future implementation
- Regular validation of license status is recommended
