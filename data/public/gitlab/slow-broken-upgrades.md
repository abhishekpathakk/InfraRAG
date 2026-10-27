# Custom Websocket Alerts

## Websocket Upgrades may be slow

- [Alert Origin](https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/17488)
- [Related Incident](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/8457)

This alert is designed to help us monitor when websocket connections cannot upgrade.
And if websocket connections cannot upgrade, real time features will not work properly.

In the originating incident, this inability to upgrade was caused by websocket requests
to `/-/cable` being cached by Cloudflare. There are possibly other situations that
could cause this alert to fire, but verifying that traffic is able to properly reach
websockets and upgrade would be a good first item to investigate.
