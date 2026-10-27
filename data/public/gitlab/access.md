# Accessing the Rails Console as an SRE

## Overview

Site Reliability Engineers (SREs) can access the `production-rails` console directly without an approval process. This document outlines two methods for accessing the console:

1. Direct SSH access (recommended)
2. Using Teleport

## Method 1: Direct SSH Access (Recommended)

### Prerequisites

Ensure your SSH is configured as described in the [gprd-bastions documentation](../bastions/gprd-bastions.md#console-access). This should have been completed during your onboarding process.

### Steps

1. Open your terminal.
2. Run the following command: `ssh <username>@gprd-console`.
3. This will directly open the `rails-console`.

## Method 2: Using Teleport

### Steps

1. Access the production Teleport instance: <https://production.teleport.gitlab.net/web>.
2. In the resource section, search for `console`.
3. Connect to the instance using your username.
4. Once connected, run the following command to access the `rails-console`: `sudo gitlab-rails console`
