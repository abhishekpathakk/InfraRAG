# macOS resources in AWS

This document outlines where most of the resources live in AWS, this can help you know where to look to debug issues.

Go to [access.md](./access.md) for information on how to access the resources described in this document.

## macOS on AWS

- [console.aws.amazon.com/ec2](https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1)
- [Amazon EC2 Mac Getting Started](https://github.com/aws-samples/amazon-ec2-mac-getting-started)
- [Detailed Background Article](https://wilsonmar.github.io/macos-aws/)
- [Mac Mini Generations](https://en.wikipedia.org/wiki/Mac_Mini)
- [IPSW File Links](https://ipsw.me/)
- [Advanced CI/CD on Headless macOS EC2](https://medium.com/@utkarsh.kapoor/advanced-ci-cd-on-headless-macos-ec2-navigating-sip-and-tcc-db-for-full-disk-access-in-gitlab-4fa98e32ac00)

### Instances

- All the macOS instances are in the 'us-east-1' region.
- All the job VMs are considered _ephemeral VMs_.
- In the case of macOS, hosts live for _at least_ 24h. This is a requirement in AWS due to macOS licensing.
- There are firewall rules between AWS and GCP (`gitlab-ci-155816` project) to allow `ssh` and other traffic from these VMs.
- See [architecture.md](../linux/architecture.md) for more details about the connections established between AWS and GCP.

### Dedicated Hosts

- [EC2 Dedicated Host Lifecycle](https://aws.amazon.com/blogs/compute/understanding-the-lifecycle-of-amazon-ec2-dedicated-hosts/)
- [Upgrading macOS Dedicated Host](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/mac-instance-updates.html)

- Perhaps the most important column in the dedicated hosts view is the `State` of each of the Hosts.
- When a host is missing `vCPU utilization` info, it could indicate the instance is deleted, but not yet deleted from the account's pool.
- _Released_ state means the instance is no longer connected to our AWS account, it's not clear how long it takes for these entries to be deleted.
- _Pending_ indicates the instance is currently being reprovisioned.

### AMIs

The images appearing in the AMI view are images that are used for provisioning the EC2 instances.

The AMIs generated here are stored in S3. See also [image building](./image_building.md).

*NOTE*: To understand the difference between an EC2 AMI and user-facing AMI, you should have a basic understanding of the architecture of these runners.
In summary, each EC2 VM you see in the console, spins up two **nested VMs** within itself.
These nested VMs use the `user facing jobs` images, while the parent instance, uses the EC2 instance images.
For more details on the architecture of these runners, have a look at [architecture.md](../linux/architecture.md).

### Volumes and Snapshots

For performance reasons, EBS Volumes are used to store job VM disk images and provide persistent storage for macOS hosts.
macOS's SIP (System Integrity Protection) prevents programmatic access to volumes without user authorization.
For example, the nesting daemon cannot access EBS volumes attached to the macOS host without said user authorization.
No API exists to bypass SIP, so we hack around it using automated VNC keyboard commands to click through permission dialogs.

More details about SIP and how we use EBS volumes in the [image building doc](./image_building.md#image-building-challenges).

- [Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volumes.html)
- [macOS SIP Settings on AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/mac-sip-settings.html)

Instance-level EBS ceilings, volume sizing and how to measure I/O performance
are covered in [performance.md](./performance.md).

### Security Groups

### Network Interfaces

### Auto Scaling Groups

## Service Quotas

[console.aws.amazon.com/servicequotas](https://us-east-1.console.aws.amazon.com/servicequotas/home?region=us-east-1#)

Quota limits for how many _dedicated_ macOS instances we can run at a time. To view these limits:

- Go to _Amazon Elastic Compute Cloud (Amazon EC2)_.
- Filter for `mac2`.
- Click _Running Dedicated mac2 Hosts_.

## S3

When job images are built in the [job-images project](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/job-images), they are uploaded to S3.

These job images are then [pulled into macOS hosts](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macos-nesting/-/blob/main/assets/nesting-start.sh#L94-94) when they are first provisioned.

More details on the method for chunking and downloading the job images can be found in the [s3pipe README](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macos-nesting/-/blob/main/cmd/s3pipe/README.md).

- [console.aws.amazon.com/s3](https://s3.console.aws.amazon.com/s3/home?region=us-east-1)

## VPC

Runner managers in GCP access macOS hosts via a redundant, 4-tunnel VPN connection that allows secure communication between GCP and AWS networks with automatic failover and dynamic routing via BGP.

- [GCP to AWS terraform configuration](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/ci-runners/fleeting-aws-env/gcp-to-aws-vpn.tf)
- [console.aws.amazon.com/vpc](https://us-east-1.console.aws.amazon.com/vpcconsole/home?region=us-east-1#Home:)
- [BGP](https://www.cloudflare.com/learning/security/glossary/what-is-bgp/)

### Route table

### Security groups

### Subnets

## IAM

[console.aws.amazon.com/iam](https://us-east-1.console.aws.amazon.com/iamv2/home?region=us-east-1#/home)

## Internal Tools

- [VNC Driver Utility](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macos-nesting/-/tree/main/cmd/vncDriver)
