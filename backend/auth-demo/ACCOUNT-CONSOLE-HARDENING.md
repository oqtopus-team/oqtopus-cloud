# Account Console password / MFA — production hardening

On-prem OQTOPUS lets a user manage **their own password and MFA** by going from
the OQTOPUS Admin / Frontend SPA to the **Keycloak Account Console**. This note
records the responsibility split, what the local demo (`compose.auth.yaml`)
implements, and what a production deployment must add before go-live.

## Responsibility split (source of truth)

| Concern | Owner | Notes |
| --- | --- | --- |
| Password (credential of record) | **OpenLDAP** | Keycloak writes through to LDAP; never a second copy in Keycloak. |
| MFA (TOTP/WebAuthn) | **Keycloak** | LDAP has no MFA concept; Keycloak stores it locally. |
| Self-service UI | **Keycloak Account Console** | `…/realms/oqtopus/account`. |
| Password policy enforcement | **OpenLDAP** (ppolicy) | Single authority — do not also enforce a conflicting policy in Keycloak (see #6). |

Rule: **no dual password management.** Keycloak federation runs `editMode=WRITABLE`
(never `UNSYNCED`, which forks the password into Keycloak-local storage).

### Where each credential lives (verified)

| Component | Stores | Verified |
| --- | --- | --- |
| OpenLDAP | the password **hash** (`userPassword: {SSHA}…`, never `{CLEARTEXT}`) | ✅ seed and post-change value are `{SSHA}` |
| Keycloak | LDAP user link (`federationLink`), MFA (TOTP/WebAuthn), sessions, audit | ✅ no local password credential (`/credentials` empty) |
| oauth2-proxy | its session cookie / tokens | — |
| OQTOPUS DB | `users.id`, status, `cognito_id`, and the **Argon2 hash** of a Q-API-Token — **no login password** | ✅ no password column in the model |
| OQTOPUS API / Frontend | nothing — the password is never received on the on-prem path | ✅ no password endpoint; proxy-mode SPA holds no token |
| Browser | only types it into the Keycloak Account Console | — |

The human password therefore exists only as an LDAP hash; the Q-API-Token (a
different credential) exists only as an Argon2 hash in the OQTOPUS DB; MFA lives
in Keycloak. The OQTOPUS app tier handles no passwords.

> AWS/Cognito caveat: the AWS-only `user_signup` service (sign-up, MFA reset)
> *receives* a password and relays it to Cognito — it never stores it, and it is
> not part of the on-prem Keycloak/LDAP topology (not deployed there).

## Demo vs. production

| Item | Demo (`auth-demo`) | Production (required) |
| --- | --- | --- |
| LDAP password write | `editMode=WRITABLE` ✅ | same |
| LDAP transport | **plaintext `ldap://openldap:389`** (demo only) | **LDAPS or StartTLS**, server-cert verified, no plaintext fallback (#2) |
| Keycloak bind account | `cn=admin` (full admin) ❌ demo only | **dedicated service account**, minimal ACL (#3) |
| Bind password | literal in `realm.json` ❌ demo only | **injected from a secret store at runtime** (#4) |
| Account Console scopes | fixed in `realm.json` ✅ | same (or config-managed Keycloak) (#5) |
| Password policy | OpenLDAP default (demo) | explicit ppolicy, documented (#6) |

The three ❌ rows are acceptable **only** in the local demo and must not reach
production.

---

## 1. LDAP federation WRITABLE — implemented

`realm.json` → `components.org.keycloak.storage.UserStorageProvider[ldap].config.editMode = "WRITABLE"`.

- A password change in the Account Console is written through to LDAP
  (`userPassword`); Keycloak keeps no local password copy.
- **`usePasswordModifyExtendedOp=true`** (RFC 3062). This matters for hashing:
  a plain LDAP *Modify* of `userPassword` (ext-op off) stores the value **as-is**
  — slapd does not hash it, so the password lands in the directory in cleartext.
  The Extended Operation instead asks the **server** to set the password, so
  slapd hashes it per `olcPasswordHash` (default `{SSHA}`). Confirm OpenLDAP
  supports the ext-op and that the `ppolicy` overlay is compatible.
- The demo seed (`demo.ldif`) stores `userPassword` as an `{SSHA}` hash, not
  cleartext, so the directory never holds a `{CLEARTEXT}` value even before any
  change.
- `UNSYNCED` is forbidden (it stores the new password in Keycloak, diverging
  from LDAP).

Verified in the demo: change password in Keycloak → old password rejected, new
password accepted by Keycloak **and** by a direct LDAP bind (`ldapwhoami`),
proving the write reached LDAP and is not Keycloak-local; and the stored
`userPassword` is `{SSHA}…` both for the seed and after a Keycloak-driven change
(never `{CLEARTEXT}`). Keycloak holds **no** local password credential for the
user (`/users/{id}/credentials` is empty; the user is `federationLink`-ed to
LDAP).

Production note: `{SSHA}` is salted SHA-1; for production prefer a stronger
scheme via the OpenLDAP password modules + `ppolicy` (e.g. `{PBKDF2-SHA512}` or
`{ARGON2}`) and set `olcPasswordHash` / the ppolicy `pwdCheckModule`
accordingly. Verify `userPassword` is never `{CLEARTEXT}` on the real server.

## 2. Encrypt Keycloak→LDAP (TLS) — production

The demo uses plaintext `ldap://`. Production **must** use one of:

- **LDAPS**: `connectionUrl = ldaps://<ldap-host>:636`
- **StartTLS**: `connectionUrl = ldap://<ldap-host>:389` + `startTls=true`

Mandatory with either:

- **Verify the server certificate.** Keycloak uses its truststore; set
  `KC_TRUSTSTORE_PATHS` (or `KC_SPI_TRUSTSTORE_FILE_*`) to a truststore holding
  the CA that signed the LDAP server cert. Do **not** set
  `useTruststoreSpi` to a mode that skips verification.
- **Never disable certificate validation** and **never allow plaintext
  fallback** (do not keep a `ldap://` connectionUrl as a backup).
- **Fail closed on TLS errors**: a cert/hostname/expiry error must fail the bind
  (no silent downgrade). This is the default once verification is on — keep it.

CA distribution / rotation:

- Ship the trusted CA to the Keycloak runtime out-of-band (config-management or a
  mounted secret), not baked into the image.
- Rotation runbook: add the new CA to the truststore → roll Keycloak →
  reissue/replace the LDAP server cert → remove the old CA. Keep an overlap
  window so no bind fails mid-rotation.

## 3. Dedicated LDAP bind (service) account — production

Do **not** use `cn=admin` as the bind DN in production. Create a dedicated
account, e.g. `cn=keycloak,ou=services,dc=oqtopus,dc=local`, with least
privilege.

Needs: search/read users & groups; read federation attributes; **modify
`userPassword` of OQTOPUS users** (and only the few attributes we write back, if
any).

Must NOT have: directory-wide admin; unrestricted create/delete of
users/groups; access to DNs unrelated to OQTOPUS; the ability to change ACLs or
`cn=config`.

Example OpenLDAP ACL (`olcAccess`) sketch — scope writes to the OQTOPUS people
subtree and to `userPassword` only:

```ldif
# userPassword: the service account may CHANGE it but must not READ it. Use
# granular privileges `=wx` (write + auth), NOT `write` — in OpenLDAP's
# cumulative model `write` implies read. With the Password Modify Ext Op the
# server performs the change and hashes it, so the account never handles the
# hash. Users may change their own; anonymous may bind (compare) to authenticate.
olcAccess: to dn.subtree="ou=people,dc=oqtopus,dc=local" attrs=userPassword
  by dn.exact="cn=keycloak,ou=services,dc=oqtopus,dc=local" =wx
  by self =wx
  by anonymous auth
  by * none
# other attributes: service account reads; users read their own; else none.
olcAccess: to dn.subtree="ou=people,dc=oqtopus,dc=local"
  by dn.exact="cn=keycloak,ou=services,dc=oqtopus,dc=local" read
  by self read
  by * none
# groups (for the role mapper): read only.
olcAccess: to dn.subtree="ou=groups,dc=oqtopus,dc=local"
  by dn.exact="cn=keycloak,ou=services,dc=oqtopus,dc=local" read
  by * none
```

Verify the account **cannot** modify a DN outside `ou=people,...` /
`ou=groups,...` (see verification #11). If using RFC 3062 ext-op, confirm the
account is permitted to run it under the ppolicy overlay.

## 4. Bind password — secret management — production

The bind password must **never** be stored in: Git files, a fixed value in
Docker Compose, Terraform code, Terraform state, a container image, or CI/CD
logs.

Inject it at runtime from the production secret store, readable **only** by the
Keycloak runtime identity:

- **Preferred:** Keycloak **Vault SPI** — put `${vault.ldap-bind-password}` as
  the `bindCredential` and back it with the files/-plaintext or HashiCorp Vault
  provider mounted as a secret. The realm config then contains a *reference*,
  not the secret.
- **Alternative:** configure the LDAP federation at deploy time via the Keycloak
  Admin API / a config tool, reading the secret from the orchestrator's secret
  manager (K8s Secret from an external store, SSM/Secrets Manager, Vault).
- Do not log the bind secret; scrub it from debug output.

Note: a full `realm.json` import stores `bindCredential` in the realm; for
production, keep the secret out of the imported JSON (use `${vault.…}` or set
the federation separately) so the committed config holds only a reference.

## 5. Account Console config reproducible — implemented

`realm.json` now makes the Account Console work after any re-import, with **no
manual `kcadm`**:

- Standard client scopes restored as realm client scopes: `web-origins`, `acr`,
  `roles`, `offline_access` (plus `basic`, `email`, `profile`).
- `defaultOptionalClientScopes = [offline_access]` now resolves (the scope is
  defined), so the import no longer logs
  `Referenced client scope 'offline_access' doesn't exist`.
- The built-in **`account` and `account-console` clients are declared
  explicitly** in `realm.json` with
  `defaultClientScopes = [web-origins, acr, profile, roles, basic, email]` and
  `optionalClientScopes = [offline_access]`. This is required because Keycloak
  does **not** apply the realm's `defaultDefaultClientScopes` to the auto-created
  built-in clients on import — verified: without the explicit client
  definitions, a fresh import leaves their default scopes empty (`[]`), which is
  exactly the "scopes are empty until a manual `kcadm` assignment" problem.
- The SPA links out to `VITE_APP_ACCOUNT_CONSOLE_URL` (= `…/realms/oqtopus/account`).

Verified: fresh realm import (force-recreate, no manual `kcadm`) →
`account` and `account-console` default scopes =
`[acr, basic, email, profile, roles, web-origins]`, console page returns 200, no
import warning. For production, keep this in `realm.json` or the equivalent
Keycloak config-management (Terraform keycloak provider / `kcadm` pipeline) so
the state is reproduced without manual steps.

## 6. Password policy — single authority — production

Enforce the policy in **OpenLDAP (`ppolicy` overlay)** and document it; do not
also set a conflicting Keycloak password policy (that would double-enforce and
confuse users). Document and set:

- Minimum length & complexity (`pwdMinLength`, plus complexity via a
  check module if required).
- History (`pwdInHistory`).
- Expiry (`pwdMaxAge`) and warning (`pwdExpireWarning`).
- Lockout (`pwdLockout`, `pwdMaxFailure`, `pwdLockoutDuration`).
- Admin reset procedure (who may reset, and whether it forces a change).
- Audit logging of password changes/resets.
- User-facing message on a failed change (map the LDAP ppolicy error to a clear
  Account Console message; avoid leaking policy internals).

State explicitly in ops docs that **LDAP ppolicy is the enforcement authority**.

## Security & network requirements

- Expose the Account Console only on the required network path (internal /
  VPN); do not publish Keycloak admin endpoints to the open internet.
- Monitor LDAP bind failures and password-change failures (alerting).
- Never log passwords, bind secrets, or tokens.
- Make password-change operations auditable (Keycloak events + LDAP audit).
- On any TLS certificate error, fail closed.

## Verification checklist (run in a prod-equivalent env)

| # | Check | How |
| --- | --- | --- |
| 1 | SPA → Account Console reachable | click "Account Settings" (proxy mode) → `…/account` loads |
| 2 | Register / remove MFA | Account Console → Signing in → set up & delete TOTP |
| 3 | Change password | Account Console → change password succeeds |
| 4 | Old password rejected | Keycloak login with old password fails |
| 5 | New password accepted | Keycloak login with new password succeeds |
| 6 | New password valid at LDAP directly | `ldapwhoami`/`ldapsearch` bind as the user with the new password |
| 7 | Not stored only in Keycloak | old pw fails *and* LDAP bind with new pw works (WRITABLE, not UNSYNCED) |
| 8 | Survives Keycloak restart/recreate | recreate Keycloak → repeat 3–6 |
| 9 | Scopes survive re-import | re-import realm → `account-console` default scopes unchanged, console loads, no warning |
| 10 | No unintended non-TLS LDAP | connectionUrl is `ldaps://` or StartTLS; a plaintext attempt is refused |
| 11 | Bind account scope-limited | the bind account cannot modify a DN outside `ou=people`/`ou=groups` |
| 12 | No AWS/Cognito regression | AWS path unchanged (Keycloak/LDAP changes don't touch Cognito or the cognito SPA driver) |

Items 1, 3–9 and 12 are demonstrated in the local demo (plaintext LDAP);
2, 10–11 and TLS-dependent parts require the prod-equivalent TLS + dedicated
bind account.

## Production apply runbook (summary)

1. Stand up OpenLDAP with `ppolicy` and the dedicated `cn=keycloak,ou=services`
   account + ACLs (#3). Issue the LDAP server TLS cert; distribute the CA (#2).
2. Load the CA into the Keycloak truststore; set `KC_TRUSTSTORE_PATHS`.
3. Provision the bind secret in the secret store; grant read only to Keycloak.
4. Apply the Keycloak config (realm import / Terraform) with
   `editMode=WRITABLE`, `ldaps://` (or StartTLS), `bindDn` = the service
   account, `bindCredential = ${vault.…}`.
5. Smoke-test the verification checklist (TLS, bind-scope, password round-trip,
   LDAP-direct bind, MFA).
6. Enable monitoring/alerts for bind + password-change failures.

## Rollback runbook

- **Config rollback:** revert the Keycloak federation to the previous known-good
  (prior realm export / Terraform state). Because the password of record lives
  in LDAP, reverting Keycloak config does **not** lose user passwords.
- **If a bad password write is suspected:** LDAP is the source of truth —
  restore from the LDAP backup/replica; Keycloak holds no divergent copy
  (WRITABLE, not UNSYNCED).
- **Emergency self-service disable:** temporarily set the federation back to
  `READ_ONLY` (Account Console password change is blocked; logins still work) and
  direct users to the admin reset procedure while investigating.
- **Never** switch to `UNSYNCED` as a workaround (it forks the password store).

## Items requiring review before production

Per the ticket, present for review: the dedicated bind account's ACLs, TLS
certificate verification config, secret management wiring, and the real-hardware
password-change test results.
