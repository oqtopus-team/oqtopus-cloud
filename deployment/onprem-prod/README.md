# OQTOPUS on-premises installation

This runbook prepares the OIST Linux host for on-site acceptance. Use the agreed
revisions of `oqtopus-cloud`, `oqtopus-frontend`, and `oqtopus-admin`. The commands
below assume sibling checkouts and rootful Docker Compose on Linux. The checked-in
realm, LDAP tree, nginx configuration, and certificates use `oqtopus.internal`
with application port 8443, admin port 8444, and Keycloak port 9443.

## Build the browser applications

Install Bun and Node.js with npm on the build machine. From
`oqtopus-cloud/deployment/onprem-prod`, install the locked dependencies and build.

```bash
(cd ../../../oqtopus-frontend && bun install --frozen-lockfile)
(cd ../../../oqtopus-admin && npm ci)
./scripts/build-spas.sh ../../../oqtopus-frontend ../../../oqtopus-admin
```

The script builds both applications in proxy mode with `/api` as the API base
and the Keycloak Account Console URL. Set `VITE_USE_USERNAME=enable` before
building if the Admin list should show display names. Compose reads the two
`dist` directories from the sibling checkouts. When distributing only the build
artifacts, set `FRONTEND_DIST` and `ADMIN_DIST` to their absolute paths in a local
Compose `.env` file.

## Install certificates and secrets

Issue certificates from the OIST-approved CA. For an isolated acceptance CA,
run `pki/gen-ca.sh oqtopus.internal` on the operator workstation. Transfer
`pki/out/ca/ca.crt` and the five leaf certificate/key pairs (`app`, `admin`,
`auth`, `ldap`, and `db`) under `pki/out/certs`. Keep the CA signing key on the
operator workstation. Distribute only `ca.crt` to client trust stores.

On the Linux host, generate fresh secrets with `sudo ./scripts/gen-secrets.sh`.
Protect the leaf keys with mode `0600` and make them root-owned. On rootful Docker
with no UID remapping, Keycloak runs as UID 1000 and oauth2-proxy as UID 65532.
Give only those readers access to the files their containers mount. The Linux
`setfacl` command is provided by the `acl` package.

```bash
sudo chown root:root pki/out/certs/*.key
sudo chmod 600 pki/out/certs/*.key
sudo setfacl -m u:1000:r pki/out/certs/auth.key \
  secrets/keycloak_db_password secrets/keycloak_admin_password \
  secrets/ldap_bind_password secrets/oauth2_proxy_client_secret \
  secrets/oauth2_proxy_admin_client_secret
sudo setfacl -m u:65532:r secrets/oauth2-proxy.cfg \
  secrets/oauth2-proxy-admin.cfg secrets/oauth2_proxy_client_secret \
  secrets/oauth2_proxy_admin_client_secret
```

Keep the secret directory private. Keep `secrets/db_app_secret.json` root-owned
with mode `0600`. Review the mapped host UIDs if deploying with UID remapping.
Reapply the per-file ACLs whenever a mounted secret or key is replaced. Check
Keycloak and both proxies start successfully on the Linux host before browser
acceptance. Use `docker compose config --quiet` to validate configuration without
printing expanded secret values.

## Initialize and start

Run the following on the Linux host from this directory. Wait for OpenLDAP to
answer on its local `ldapi` socket before applying its password policy and ACLs.
Proceed to the final `up` after the policy script reports success. Compose gates
API startup on the MySQL migration and SeaweedFS bucket creation.

```bash
sudo docker compose config --quiet
sudo docker compose up -d --wait db openldap
sudo docker compose exec -T openldap ldapwhoami -Y EXTERNAL -H ldapi:///
sudo ./scripts/apply-ldap-config.sh
sudo docker compose up -d --build
sudo docker compose ps -a
```

On the acceptance workstation, map `app.oqtopus.internal`,
`admin.oqtopus.internal`, and `auth.oqtopus.internal` to `127.0.0.1` and trust the
CA. Forward the loopback-bound services from the Linux host over SSH. Port 9443
also carries the Keycloak management interface, so restrict this tunnel to
acceptance operators.

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:8443:127.0.0.1:8443 \
  -L 127.0.0.1:8444:127.0.0.1:8444 \
  -L 127.0.0.1:9443:127.0.0.1:9443 \
  <operator>@<oist-host>
```

Open the User and Admin SPAs at `https://app.oqtopus.internal:8443/` and
`https://admin.oqtopus.internal:8444/`. After directory and device provisioning,
check first-login password change and MFA, approval, device listing, then job
registration, ZIP upload, submission, and retrieval of the job detail. The two
SPA origins serve signed storage requests. Access logging for those routes
records only method and status, and each upload is limited to 10 MiB including
multipart fields.

For acceptance, provision only test accounts. The branch provides
`oqtopus-cloud-ops user-add`, which writes the temporary password to a private
file. The directory stores the user's email and the `oqtopus-admin` LDAP group
controls Admin access. In the Mac test the operator verified the test fixture's
email and marked it verified in Keycloak, then assigned the admin fixture to
that group. Repeat the verification for the OIST acceptance accounts. General
access needs an agreed, tested workflow for email verification and admin
provisioning, including session revocation.

## Before general access

Use the [implementation plan](../../オンプレ認証本番公開までの実装計画.md)
for release gates. The loopback setup above is for operator acceptance. General
access requires the agreed OIST network ingress and a protected Keycloak
management path. Complete lifecycle tests for user suspension and admin
revocation, CLI token tests, Keycloak-to-MySQL certificate identity verification,
image digest pinning, and the backup restore test before go-live.

Run `scripts/ci/onprem_prod_guard.sh` from the repository root to validate the
production configuration against the demo-setting rules.
