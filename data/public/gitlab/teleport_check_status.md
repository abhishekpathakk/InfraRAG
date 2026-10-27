# Checking Status of Teleport

All the services comprise a Teleport cluster are stateless.

- All certificates and keys are stored in
  [KMS](https://console.cloud.google.com/security/kms/keyring/manage/us/gitlab-teleport-teleport-production/key?project=gitlab-teleport-production).
- The cluster internal state and audit events are stored in
  [Firestore](https://console.cloud.google.com/firestore/databases/-default-?project=gitlab-teleport-production).
- The [session recordings](https://goteleport.com/docs/architecture/session-recording/) are stored in a Cloud Storage
  [bucket](https://console.cloud.google.com/storage/browser/gl-teleport-production-teleport-sessions?project=gitlab-teleport-production).

You can check the status of the production Teleport cluster by running the following command,
after running `glsh kube use-cluster ops-central` command in a separate shell:

```
$ kubectl exec --namespace=teleport-cluster-production --stdin --tty <teleport-production-auth-pod> -- tctl status
```

<details>
<summary>Example output</summary>

```
Cluster       production.teleport.gitlab.net
Version       16.1.7
host CA       never updated
user CA       never updated
db CA         never updated
db_client CA  never updated
openssh CA    never updated
jwt CA        never updated
saml_idp CA   never updated
oidc_idp CA   never updated
spiffe CA     never updated
CA pin        sha256:d4ac1c9af5d25e6cf3c60c8078efe443c1186c071c99641dcd9b11eb0831f46d
```

</details>

Generally, if the pods are healthy, then the service is healthy.
