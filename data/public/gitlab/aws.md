# AWS Managed Certificates

The only certificate currently managed by AWS is the `snowplowstg.trx.gitlab.net` certificate. It is not currently terraform managed.
The `snowplow.trx.gitlab.net` is currently an SSLMate certificate that has been uploaded to the cert manager.

The loadbalancer can be accessed in the [AWS Console](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1)
