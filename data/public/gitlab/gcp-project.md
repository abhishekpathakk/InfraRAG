# GCP Projects

## New Project Creation

The following assumes you want to utilize our existing infrastructure as much as
feasibly possible.  This includes the use of our existing terraform and chef
infrastructure.

The following documentation only covers what is required to bootstrap an
environment.  This includes what is necessary in terraform and GCP prior to
starting up your first instance in that project.  Details of what is created
inside of that project will not be discussed as that is implementation specific.

1. Follow the documentation here: <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/HOWTO.md#create-an-environment>
    * This will build out the framework for the project and it's requirements
1. Create two service accounts in GCP:
    * `terraform`
    * `google-object-storage`
    1. Navigate to your new project
    1. Browse to `IAM` > `Service Accounts`
    1. Click `Create Service Account`
    1. Fill in the following fields with the same data for each account:
        * `Service account name`
        * `Service account ID`
        * `Service account description`
    1. When completed, on the main `Service Account` screen, you'll see your new
       account listed.
    1. Ensure the email address of the account is what is expected.  This is the
       format `<serviceAccountName>@<ENV>.iam.gserviceaccount.com`
1. Create the bootstrap Key ring framework
    1. Browse to `IAM` > `Cryptographic keys`
    1. Click `Create Key Ring`
    1. Utilize the name `gitlab-<ENV>-boostrap` - example `gitlab-pre-bootstrap`
        * This is required as our chef bootstrap script require this
          nomenclature
        * Utilize a `global` Key ring location
    1. Click `Create`
    1. On the next screen utilize these details:
       * `Generated Key`
       * `Key name`: `gitlab-<ENV>-bootstrap-validation`
       * Protection Level: `Software`
       * Purpose: `Symmetric encrypt/decrypt`
       * Rotation: `90 days`
       * Utilize the default rotation start date
    1. Click `Create`
1. Create the chef Key ring framework
    1. Browse to `IAM` > `Cryptographic keys`
    1. Click `Create Key Ring`
    1. Utilize the name `gitlab-secrets`
        * This is required as our chef bootstrap script require this
          nomenclature
        * Utilize a `global` Key ring location
    1. Click `Create`
    1. On the next screen utilize these details:
       * `Generated Key`
       * `Key name`: `<ENV>`
       * Protection Level: `Software`
       * Purpose: `Symmetric encrypt/decrypt`
       * Rotation: `90 days`
       * Utilize the default rotation start date
    1. Click `Create`
1. Provide the terraform service account permissions to the new key and keyring
    1. Perform the following on both keyrings created in the prior step
    1. Navigate to `IAM` > `Cryptographic Keys`
    1. Select our newly created Key Ring
    1. On the panel to the right click `Add Member`
    1. The new member would be `terraform@gitlab-<ENV>.iam.gserviceaccount.com`
    1. The new role would be `Cloud KMS CryptoKey Decryptor`
    1. Click `Save`
1. Encrypt our chef `validation.pem` file and upload it to our bootstrap bucket
   for the new project
    1. Download the validator private key from 1password
       * Search for `validator-gitlab`
       * Copy the `PRIVATE-KEY` to a file locally `validation.pem`
    1. Encrypt the file using our newly created key ring
       * `gcloud kms encrypt \
            --ciphertext-file=validation.enc \
            --plaintext-file=validation.pem \
            --key gitlab-<ENV>-boostrap-validation \
            --keyring gitlab-<ENV>-bootstrap \
            --location global`
      * Delete the `validation.pem` file
      * Upload the `validation.enc` to our bucket
        * `gsutil cp validation.enc
          gs://gitlab-<ENV>-chef-bootstrap/validation.enc`
1. You may now proceed to creating instances in your new project
    * The project will be in a directory named the same as `<ENV>` at this path:
      <https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/tree/main/environments>
    * You'll also want the necessary chef-roles to go along with this
      environment, which will be placed at this path:
      `https://gitlab.com/gitlab-com/gl-infra/chef-repo/-/tree/master/roles`

### Future Work

* Some of the above will be removed with work to be completed here: <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/8165>

## Project Deletion

Assuming you followed the instructions above to create the project and used Terraform to create resources in it, deleting/decommissioning the project should be a simple matter of deleting the Terraformed infrastructure first, then removing the project itself.

1. Ensure you've run the `config-mgmt/bin/tf-get-secrets` script.
1. Navigate to the directory in `config-mgmt/environments` that contains the resource definitions for infrastructure in the project and make sure you've initialised Terraform by running `tf init`.
1. To see a list of everything Terraform manages in the environment (project), run `tf state list`.
1. Pick something innocuous from the list (something that shouldn't cause too much harm if it got into a bad state) and try destroying it using `tf destroy -target <thing to destroy>`.
    * For example, if you have a bunch of resources under `module.prometheus-app`, run `tf destroy -target module.prometheus-app`.
    * Don't forget the `-target` option!
    * You're likely to run into errors when destroying things, which is why we're destroying only one resource to begin with. If you get errors where resources require `force_destroy = true` (for example when trying to delete a non-empty storage bucket), if the module doesn't allow changing this as a variable, you might need to go into the module code in `.terraform/modules` and change `force_destroy` there.
    * If there are retention policies stopping you from deleting buckets, we'll deal with them later when we delete the project.
    * Don't delete the bucket named `<env>-secrets` otherwise you're gonna have a bad time later (Terraform needs those secrets).
1. Eventually you should be able to destroy everything in one go by targeting the environment: `tf destroy -target module.<env>`. Once this is done, remove the directory containing the TF resource definitions and commit your changes to a new branch.
1. We'll deal with the Chef nodes next. In `chef-repo`, run `knife status` to get a list of all the Chef nodes in the project.
    * You'll need to run `knife client delete` and `knife node delete` on all of them.
    * Use the `-y` flag to auto confirm deletion if there are a lot of nodes to get through.
1. Remove the Chef roles for the environment in `chef-repo`, commit and raise an MR for your changes.
1. Next, move to `config-mgmt/environments/env-projects`. Run `tf init` again if you need to, then run `tf destroy -target module.<env>`. This will hopefully delete the entire project. Then remove the environment from the definition files and commit your changes.
    * If you get an error about liens preventing the deletion, remove the offending lien by following the instructions [here](https://docs.cloud.google.com/resource-manager/docs/project-liens#removing_liens_from_a_project).
1. Remove the environment from the CI pipelines otherwise they'll error out trying to initialise state for something that doesn't exist. Look for occurrences of the environment name in `.gitlab/ci` and remove them all. Commit your changes.
1. If the project no longer shows up in the UI, you're almost done! **Remember to raise MRs for your changes and get them merged.**
