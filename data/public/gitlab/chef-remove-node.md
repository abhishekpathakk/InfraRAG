# Chef Remove Node

This runbook describes how to safely remove a node from Chef Server when a VM or service has been decommissioned or renamed. It is intended for routine fleet hygiene (e.g., Terraform destroys, stale node cleanup) so Chef’s view of infrastructure matches reality.

This runbook applies to:

- Nodes managed by chef.gitlab.com

## Identify the node name

Use the node’s FQDN as registered in Chef, which typically matches the VM’s internal DNS name. Also identify the client as each node has a corresponding client. To find the FQDN, from the root of your local chef-repo:

```shell
knife node list | grep <PATTERN>
knife client list | grep <PATTERN>
```

Use `knife client list` if you have a situation where the node doesn't exist but a client still does. Proceed with only deleting the client in this case.

## Remove the node

Remove the node and corresponding client from Chef Server using knife:

```shell
knife node delete <NODE_FQDN> -y
knife client delete <NODE_FQDN> -y
```

Note: Use `-y` in scripted / bulk cleanup to avoid interactive prompts (as used in production change scripts).

## verification

Verify the node is gone

From the root of your local chef-repo:

```shell
knife node show <NODE_FQDN>
knife client show <NODE_FQDN>
```

Both commands should return error messages indicating the node and client are not found, confirming successful removal.
