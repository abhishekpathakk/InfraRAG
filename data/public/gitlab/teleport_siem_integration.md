# Teleport SIEM Integration

The `teleport-plugin-event-handler` is used for handling Teleport audit events and sending them to a [Fluentd](https://www.fluentd.org/) instance,
so such events can be further shipped to other systems (i.e. SIEM) for security and auditing purposes.
Read more about exporting Teleport audit events [here](https://goteleport.com/docs/zero-trust-access/export-audit-events/). See this [guide](https://goteleport.com/docs/management/export-audit-events/fluentd/) and
[this](https://github.com/gravitational/teleport-plugins/tree/master/event-handler) one for further instructions.

- This plugin is installed using
  [teleport-plugin-event-handler](https://goteleport.com/docs/reference/helm-reference/teleport-plugin-event-handler/) Helm chart
  (see [here](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/service.yaml)).
- The following roles and user are created via the
  [teleport-bootstrap](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/main/services/teleport-cluster/charts/teleport-cluster-config/templates/event-handler.yaml) chart.
  - Role `event-handler-events-sessions-viewer`
  - Role `bot-event-handler-bot`
  - Bot `event-handler-bot`
  - Join token `event-handler-bot-token`

## Configuring mTLS Communication

The `teleport-plugin-event-handler` requires *Mutual TLS* connection be enabled on `fluentd` instance for security purposes.
The certificate authority, server key and certificate, and client key and certificate are stored in Vault at
`k8s/ops-gitlab-gke/teleport-cluster-staging/fluentd-certs` and `k8s/ops-central/teleport-cluster-production/fluentd-certs`.

For renewing the certificates, create the following files in a directory.

<details>
<summary>openssl.conf</summary>

```conf
[req]
default_bits        = 4096
distinguished_name  = req_distinguished_name
string_mask         = utf8only
default_md          = sha256
x509_extensions     = v3_ca

[req_distinguished_name]
countryName            = Country Name (2 letter code)
stateOrProvinceName    = State or Province Name
localityName           = Locality Name
0.organizationName     = Organization Name
organizationalUnitName = Organizational Unit Name
commonName             = Common Name
emailAddress           = Email Address

countryName_default            =
stateOrProvinceName_default    =
localityName_default           =
0.organizationName_default     = GitLab Inc.
organizationalUnitName_default = Teleport
commonName_default             = localhost
emailAddress_default           =

[v3_ca]
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid:always,issuer
basicConstraints       = critical, CA:true, pathlen: 0
keyUsage               = critical, cRLSign, keyCertSign

[client_cert]
basicConstraints       = CA:FALSE
nsCertType             = client, email
nsComment              = "OpenSSL Generated Client Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
keyUsage               = critical, nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage       = clientAuth, emailProtection

[crl_ext]
authorityKeyIdentifier = keyid:always

[ocsp]
basicConstraints       = CA:FALSE
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer
keyUsage               = critical, digitalSignature
extendedKeyUsage       = critical, OCSPSigning

[staging_server_cert]
basicConstraints       = CA:FALSE
nsCertType             = server
nsComment              = "OpenSSL Generated Server Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth
subjectAltName         = @staging_alt_names

[staging_alt_names]
DNS.0 = teleport-staging-fluentd-headless.teleport-cluster-staging.svc.cluster.local
DNS.1 = *.teleport-staging-fluentd-headless.teleport-cluster-staging.svc.cluster.local
DNS.2 = teleport-staging-fluentd-aggregator.teleport-cluster-staging.svc.cluster.local
DNS.3 = *.teleport-staging-fluentd-aggregator.teleport-cluster-staging.svc.cluster.local

[production_server_cert]
basicConstraints       = CA:FALSE
nsCertType             = server
nsComment              = "OpenSSL Generated Server Certificate"
subjectKeyIdentifier   = hash
authorityKeyIdentifier = keyid,issuer:always
keyUsage               = critical, digitalSignature, keyEncipherment
extendedKeyUsage       = serverAuth
subjectAltName         = @production_alt_names

[production_alt_names]
DNS.0 = teleport-production-fluentd-headless.teleport-cluster-production.svc.cluster.local
DNS.1 = *.teleport-production-fluentd-headless.teleport-cluster-production.svc.cluster.local
DNS.2 = teleport-production-fluentd-aggregator.teleport-cluster-production.svc.cluster.local
DNS.3 = *.teleport-production-fluentd-aggregator.teleport-cluster-production.svc.cluster.local
```

</details>

<details>
<summary>Makefile</summary>

```makefile
key_len        := 4096
staging_dir    := staging
production_dir := production

.PHONY: gen-staging
gen-staging:
  mkdir -p $(staging_dir)
  rm -f $(staging_dir)/*

  openssl genrsa -out $(staging_dir)/ca.key $(key_len)
  chmod 444 $(staging_dir)/ca.key
  openssl req -config openssl.conf -key $(staging_dir)/ca.key -new -x509 -days 3650 -sha256 -extensions v3_ca -subj "/CN=ca" -out $(staging_dir)/ca.crt

  openssl genrsa -out $(staging_dir)/client.key $(key_len)
  chmod 444 $(staging_dir)/client.key
  openssl req -config openssl.conf -subj "/CN=teleport-event-handler" -key $(staging_dir)/client.key -new -out $(staging_dir)/client.csr
  openssl x509 -req -in $(staging_dir)/client.csr -CA $(staging_dir)/ca.crt -CAkey $(staging_dir)/ca.key -CAcreateserial -days 365 -out $(staging_dir)/client.crt -extfile openssl.conf -extensions client_cert

  openssl genrsa -out $(staging_dir)/server.key $(key_len)
  chmod 444 $(staging_dir)/server.key
  openssl req -config openssl.conf -subj "/CN=fluentd-aggregator" -key $(staging_dir)/server.key -new -out $(staging_dir)/server.csr
  openssl x509 -req -in $(staging_dir)/server.csr -CA $(staging_dir)/ca.crt -CAkey $(staging_dir)/ca.key -CAcreateserial -days 365 -out $(staging_dir)/server.crt -extfile openssl.conf -extensions staging_server_cert

.PHONY: gen-production
gen-production:
  mkdir -p $(production_dir)
  rm -f $(production_dir)/*

  openssl genrsa -out $(production_dir)/ca.key $(key_len)
  chmod 444 $(production_dir)/ca.key
  openssl req -config openssl.conf -key $(production_dir)/ca.key -new -x509 -days 3650 -sha256 -extensions v3_ca -subj "/CN=ca" -out $(production_dir)/ca.crt

  openssl genrsa -out $(production_dir)/client.key $(key_len)
  chmod 444 $(production_dir)/client.key
  openssl req -config openssl.conf -subj "/CN=teleport-event-handler" -key $(production_dir)/client.key -new -out $(production_dir)/client.csr
  openssl x509 -req -in $(production_dir)/client.csr -CA $(production_dir)/ca.crt -CAkey $(production_dir)/ca.key -CAcreateserial -days 365 -out $(production_dir)/client.crt -extfile openssl.conf -extensions client_cert

  openssl genrsa -out $(production_dir)/server.key $(key_len)
  chmod 444 $(production_dir)/server.key
  openssl req -config openssl.conf -subj "/CN=fluentd-aggregator" -key $(production_dir)/server.key -new -out $(production_dir)/server.csr
  openssl x509 -req -in $(production_dir)/server.csr -CA $(production_dir)/ca.crt -CAkey $(production_dir)/ca.key -CAcreateserial -days 365 -out $(production_dir)/server.crt -extfile openssl.conf -extensions production_server_cert
```

</details>

Run the `make gen-staging` command for generating certificates for the `teleport-staging` cluster,
and the `make gen-production` command for the `teleport-production` cluster.
Next, update the Vault secret as follows.

```bash
$ vault login -method oidc
$ vault kv put k8s/ops-central/teleport-cluster-production/fluentd-certs \
    ca.crt="$(cat ca.crt)" \
    server.crt="$(cat server.crt)" \
    server.key="$(cat server.key)" \
    client.crt="$(cat client.crt)" \
    client.key="$(cat client.key)"
```

Finally, get the latest secret version from the Vault and update the `teleport-cluster` release
[here](https://gitlab.com/gitlab-com/gl-infra/argocd/apps/-/blob/74a75f33bb3e36c089241d02b7dafc1a89fc7da1/services/teleport-cluster/values-vault-secrets.yaml#L23).

## Google Cloud Pub/Sub Configurations

Fluentd uses [fluent-plugin-gcloud-pubsub-custom](https://github.com/mia-0032/fluent-plugin-gcloud-pubsub-custom) gem
for sending the audit events to the following Google Cloud Pub/Sub topics:

- `projects/gitlab-teleport-staging/topics/teleport-staging-events`
- `projects/gitlab-teleport-production/topics/teleport-production-events`

We use a custom-built OCI (Docker) image with the `fluent-plugin-gcloud-pubsub-custom` gem baked into the image.
You can update/modify this image [here](https://gitlab.com/gitlab-com/gl-infra/ci-images/-/tree/master/fluentd).

We use [Workload Identity](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
for authenticating to Google Cloud. The *Workload Identity* is configured
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/teleport-cluster/service-account.tf)
and the required *Roles* are configured
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/modules/teleport-project/pubsub.tf).
