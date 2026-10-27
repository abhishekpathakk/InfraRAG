# Gitaly Repository Export

Developers might need the disk represenation of a repository in a Gitaly server
for debugging purpose. Below is a step by step guide on how to do it. At the
moment this is all manual, we plan to automate/self-serve this in
<https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16833>

Previous examples:

- <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16828>
- <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/16674>
- <https://gitlab.com/gitlab-com/gl-infra/production-engineering/-/issues/17469>

1. Locate repository location

    ```shell
    ssh $USER-rails@console-01-sv-gprd.c.gitlab-production.internal
    [ gprd ] production> p = Project.find_by_full_path("gitlab-org/gitlab")
    => #<Project id:278964 gitlab-org/gitlab>>
    [ gprd ] production> p.repository.storage
    => "nfs-file-cny01"
    [ gprd ] production> p.repository.disk_path
    => "@hashed/a6/80/a68072e80f075e89bc74a300101a9e71e8363bdb542182580162553462480a52"
    [ gprd ] production> p.pool_repository.disk_path # When a project gets forked, a pool repository is created we need to export it as well
    => "@pools/b4/3e/b43ef5538f2e6167fdc8852badbe497b50d4cfd4ed7e1b033068f1a296ee57d2"
    ```

1. Create tar file of that repository

    ```shell
    ssh file-cny-01-stor-gprd.c.gitlab-production.internal
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ sudo tar -cf gitlab-org-gitlab.tar /var/opt/gitlab/git-data/repositories/@hashed/a6/80/a68072e80f075e89bc74a300101a9e71e8363bdb542182580162553462480a52.git /var/opt/gitlab/git-data/repositories/@pools/b4/3e/b43ef5538f2e6167fdc8852badbe497b50d4cfd4ed7e1b033068f1a296ee57d2.git
    ```

1. Create new key for the
   `gitaly-repository-exporter@gitlab-production.iam.gserviceaccount.com` to
   use it to upload the tar file to GCS. Then copy them to the Gitaly node.

    ```shell
    gcloud --project=gitlab-production iam service-accounts keys create credenitals-gitaly-repository-exporter-tmp.json --iam-account=gitaly-repository-exporter@gitlab-production.iam.gserviceaccount.com
    created key [08b258a674345d5d8e20ec9ca44182b1d135eaad] of type [json] as [credenitals-gitaly-repository-exporter-tmp.json] for [gitaly-repository-exporter@gitlab-production.iam.gserviceaccount.com]
    scp credenitals-gitaly-repository-exporter-tmp.json file-cny-01-stor-gprd.c.gitlab-production.internal:/home/$USER/
    ```

    At this moment in your home directory you should have a tar and the credentials.

    ```shell
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ ls
    credenitals-gitaly-repository-exporter-tmp.json  reliability-17469.tar
    ```

1. Activate service account key and upload the tar file.

    ```shell
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ gcloud auth activate-service-account --key-file credenitals-gitaly-repository-exporter-tmp.json
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ gsutil cp reliability-17469.tar gs://gitlab-gstg-gitaly-repository-exporter/
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ gcloud config set account terraform@gitlab-production.iam.gserviceaccount.com
    steve@file-cny-01-stor-gprd.c.gitlab-production.internal:~$ rm credenitals-gitaly-repository-exporter-tmp.json
    ```

1. Sign the URL locally, we don't do it on the server because we might not have
   all the dependencies.

    ```shell
    gsutil signurl credenitals-gitaly-repository-exporter-tmp.json gs://gitlab-gstg-gitaly-repository-exporter/reliability-17469.tar
    ```

    Share the generated URL with the developer

1. Clean up local credentials

    ```shell
    rm credenitals-gitaly-repository-exporter-tmp.json
    gcloud --project=gitlab-production iam service-accounts keys delete 08b258a674345d5d8e20ec9ca44182b1d135eaad --iam-account=gitaly-repository-exporter@gitlab-production.iam.gserviceaccount.com
    ```
