# Manage DNS entries

We use Route 53 and/or Cloudflare [depending on zone](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/dns-record/-/blob/master/zones.json) to manage DNS entries in our hosted zones through the terraform
environment `dns` on <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt> and also thoughout other environments for terraform bound DNS entries.

## Create, edit or delete DNS entries

- Check if the hosted zone and record type you're targeting is already in
[variables.tf](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/master/environments/dns/variables.tf).
If not, create the variable ([and add the zone](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/dns-record#zone-configuration)) and get the zone id from AWS and/or Cloudflare, depending on the zone.
- Establish the variable in which your entry should go. We're using
`"<zone-name>".auto.tfvars.json` files with variables called
`"<zone-name>_<record_type>"` in them. So for example if you were to add a CNAME
record to gitlab.com you'd edit the `gitlab_com_cname` variable on the
[`gitlab_com.auto.tfvars.json` file](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/master/environments/dns/gitlab_com.auto.tfvars.json)
- Create a Merge Request with your changes and ask the SRE team for approval

If your record is dependent on the output from creating another terraform resource (e.g. a load balancer), prefer using the [dns-record module](https://ops.gitlab.net/gitlab-com/gl-infra/terraform-modules/dns-record) directly alongside that other resource, rather than managing the record in the `dns` environment indepedently

## Non-SRE updates to gitlab.com subdomains and DNS records

1. Create a new branch in [config-mgmt](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/branches/new) named `{username}/dns-{subdomain}-gitlab-com` (ex. `dmurphy/dns-example-gitlab-com`). If you do not have access, ask in [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N) for help.
1. At the top of the page, click **Create merge request**
    - Change the title to `DNS {subdomain}.gitlab.com`.
    - Add a justification message between the `Terraform merge-request checklist` and `General` headings.
    - Click the **Assign to me** button.
    - Click the **Create merge request** button.
1. On the merge request page, click the **Code** button in the top right corner and **Open in Web IDE**.
    - Open the `environments/dns/gitlab_com.auto.tfvars.json` file.
    - Each type of record has a section (ex. `gitlab_com_a`, `gitlab_com_caa`, `gitlab_com_txt`, etc.). It is helpful to collapse these sections using the caret next to the line number in the left gutter, starting with Line 2.
1. For each type of record (CNAME, TXT, etc) in the issue
    - Expand the section for the type of record.
    - Use Cmd+F/Ctrl+F to search for the record name to ensure it doesn't already exist. If it does, stop and evaluate whether you are updating the same system or a different system. You can use the Blame button (outside of the Web IDE) to see a full history and trace back the MR and any linked issue from when this was added. It is best practice to tag the previous requester (if they are still at GitLab) or the manager of the department/team that manages this service (cross reference the tech stack). Do not proceed until you understand how the existing service will break.
    - Scroll to the bottom of the array of records
    - Copy and paste the last record (to re-use the same formatting without making a syntax typo).
    - To ensure validate JSON syntax, add a comma after the `}` for the record that you just copied from. The last record will not have a trailing comma, however all records in the array will have a comma.
    - Update the JSON key (ex. `"old-record.gitlab.com": {` to include the full FQDN of the subdomain (ex. `example.gitlab.com`).
    - Update the `records` array with the value of the value of this record.
        - For CNAME records, ensure that you do not include any `https://` or trailing `/` or paths. This is a FQDN (domain name).
    - You do not need to edit the TTL.
1. Repeat the steps above for each of the records being requested.
1. Commit the changes
1. On the Merge Request page, open the pipeline (in a new tab) that was triggered by the last commit.
    - Open the `plan` stage > `review dns` job CI output.
    - Wait for the job to finish.
    - If successful, scroll up and look at Terraform `Plan: # to add, # to change, # to destroy.
    - This should **only** have the changes that you explicitely want. Anything unexpected means that you should stop and perform a peer review to understand what is changing and why. A successful result will look like `Plan: 1 to add, 0 to change, 0 to destroy`.
1. Check the box on the merge request `Plan has been reviewed and has no unexpected changes`.
1. Navigate to the changes tab of the merge request. (Optional) Take a screenshot of the lines and add the screenshot as a comment to the your team's issue related to what you're working on.
1. Post in [#production_engineering](https://gitlab.enterprise.slack.com/archives/C03QC5KNW5N) - `Can I please get a review/approval/merge/apply on config-mgmt!#### for a new DNS record? Thank you!`
