# macOS Images

## Image Building Projects

- **[macOS with nesting AMI](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macOS-nesting)**
  - Builds and publishes macOS AMIs for dedicated hosts
  - Uses Packer with AWS instance plugin
  - Based on Amazon macOS AMI with EC2 utilities

- **[macOS job images build machine](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/macOS-build-machine)**
  - Dedicated always-on Mac host for building images
  - Attached to job images build project

- **[macOS job images automation](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/job-images)**
  - Uses Packer and Tart for image building
  - Publishes images to S3
  - Combines macOS base image, Xcode tools, and Ansible-installed packages

## Job Image Logging

We have enabled `FF_LOG_IMAGES_CONFIGURED_FOR_JOB` on macOS runners, which causes the runner to log the image name selected for each job.

To see which job images are actively being used, query Elastic using the `pubsub-runner-inf-gprd*` data view and filter by:

- `json.shard.keyword`: restrict to the macOS shard of interest, e.g. `saas-macos-medium-m1`
- `json.image_name.keyword`: set to `*` to match any job that logged an image name

This lets you identify which images are in active use across a shard.

## Image Building Challenges

**Manual Intervention Required**: Building job images isn't fully automated due to:

- Xcode installation requiring Apple Developer login with 2FA
- Large host images and Xcode packages requiring persistent EBS storage

**Storage Considerations**: Originally, all job VMs were baked into the host AMI, creating large images with lazy EBS loading issues. The solution involves:

- Using empty EBS volumes
- Downloading images at startup
- Trading ~10 minutes of provisioning time for full EBS performance

### System Integrity Protection (SIP)

**The Problem**: macOS SIP prevents programs from accessing volumes without user authorization, with no scriptable API.

**The Solution**: Automated keyboard commands over VNC to handle authorization dialogs.

- Implemented in [nesting full disk access script](https://gitlab.com/gitlab-org/ci-cd/shared-runners/images/aws/macos-nesting/-/blob/main/scripts/30_nesting_full_disk_access.sh#L58)
- ~20% failure rate, but acceptable given build frequency
- Recent AWS SIP control updates may enable programmatic disabling during AMI building
