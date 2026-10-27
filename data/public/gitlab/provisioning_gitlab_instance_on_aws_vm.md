# Provisioning a GitLab Instance on an AWS VM

This tutorial provides step-by-step instructions for provisioning a GitLab instance on an AWS EC2 VM using the GitLab Sandbox Cloud.

## Prerequisites

- Access to [GitLab Sandbox Cloud](https://gitlabsandbox.cloud/)
- Okta credentials for authentication
- SSH key pair for EC2 instance access (can also be created during EC2 instance launch)

## Steps

### 1. Access GitLab Sandbox Cloud

1. Go to <https://gitlabsandbox.cloud/> and login with Okta
2. Create an account if you don't have one with the following settings:
   - **Cloud provider**: `aws-51eab1fa` (Master Account)
   - **Organizational Unit**: `eng-infra-sandbox`

### 2. Access Your AWS Account

When the account has been created (or if you already had one):

1. Access it by clicking on your account in the Sandbox Cloud dashboard
2. Use the **Open AWS Web Console** button in your Cloud Account page
3. Log in to the AWS account using the username and password from **View IAM Credentials**

### 3. Launch an EC2 Instance

1. Go to **EC2** in the AWS Console
2. Click **Launch instance**
3. Configure the instance:
   - Give it a name
   - Select **Ubuntu** as the AMI
   - Select instance type **t2.medium or larger** (GitLab requires a minimum of 4 GB RAM)
   - Select or create a key pair. If creating a new key pair, download the `.pem` file immediately — you will need it for SSH access later
4. Under **Network settings**, allow HTTP/HTTPS traffic from the internet
5. Configure storage: **50 GiB gp2/gp3** (NOT iops)
6. Click the **Launch instance** button on the right
7. Go to your instances to see info about the created instance

### 4. Install GitLab

You can install GitLab using one of two methods:

#### Option A: Manual Installation

1. If you created your key pair using the AWS dashboard, update the key file permissions first:

   ```bash
   chmod 600 <absolute-path-to-ssh-key>
   ```

2. SSH into the instance:

   ```bash
   ssh -i <absolute-path-to-ssh-key> ubuntu@<public-dns-of-the-instance>
   ```

3. Follow the instructions to install GitLab: <https://docs.gitlab.com/install/package/ubuntu/>

#### Option B: Using OpenCode (Recommended)

Use this prompt with OpenCode:

> SSH into `ubuntu@<public-dns-of-the-instance>` and install GitLab following <https://docs.gitlab.com/install/package/ubuntu/>. To SSH into the VM use this key: `<absolute-path-to-ssh-key>`

## Dealing with Machine Restarts

When stopping and starting EC2 instances, a new IP address and hostname is assigned to the instance. You can fix this in one of two ways:

### Option 1: Assign an Elastic IP (Recommended for Persistent Use)

Assign your EC2 instance an Elastic IP to make the IP static.

> **Note**: Elastic IPs may incur additional costs.

### Option 2: Update GitLab Configuration

Once the machine is running again:

1. Update the `external_url` parameter in `/etc/gitlab/gitlab.rb` to point to the new hostname:

   ```ruby
   external_url 'http://<new-public-dns-of-the-instance>'

2. Run the following commands:

   ```bash
   sudo gitlab-ctl reconfigure
   sudo gitlab-ctl restart
   ```

3. The instance is now available on the new hostname

## Learn More

- [GitLab Installation Documentation](https://docs.gitlab.com/install/)
- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [GitLab Sandbox Cloud](https://gitlabsandbox.cloud/)
