# Flexible Auth Demo — OIDC (oauth2-proxy + Keycloak + LDAP)

This demo runs the OQTOPUS **User API** locally with authentication decoupled
from AWS Cognito. Instead, the browser authenticates against a standard **OIDC**
provider (Keycloak), which federates an internal **LDAP** directory, fronted by
**oauth2-proxy**. The API no longer depends on Amplify/Cognito — it just verifies
an OIDC JWT and enforces its own authorization.

## Why this exists

The requirement is to deploy the whole stack **on an internal network without
AWS**, letting the SPA drop its Cognito/Amplify dependency and authenticate via
any OIDC-compliant server (and, behind it, LDAP). We split the concerns the way
the AWS Lambda authorizer already did — just relocated:

| Concern | AWS (prod) | This demo (local / on-prem) |
| --- | --- | --- |
| **Authentication** (who are you?) | API Gateway → Lambda authorizer verifies Cognito JWT | **oauth2-proxy + Keycloak (+ LDAP)**; the API verifies the OIDC JWT |
| **Authorization** (may you in?) | Lambda authorizer: DB `userstatus == approved` | **In-app** middleware: same DB check (`common/auth/authorization.py`) |
| **Identity contract** | `authorizer["user_id"]` (= email) | `email` claim → `request.state.user_id` (unchanged downstream) |

The switch is the `AUTH_MODE` environment variable (`aws` | `oidc` | `local`).
`ENV=local` still controls DB/storage wiring only — auth is now independent.

## Topology

```
Browser
  └─(session cookie)─▶ oauth2-proxy  :4180   ── OIDC ──▶ Keycloak :8081
                          │                                  └─ LDAP federation ─▶ OpenLDAP :389
                          └─(Authorization: Bearer <id_token>)─▶ user-api :8080
                                                                   ├─ verify JWT vs Keycloak JWKS
                                                                   ├─ user_id = email claim
                                                                   └─ authorize: users.userstatus == approved
```

## Prerequisites

- Docker + Docker Compose
- Run from the `backend/` directory

## Start

```bash
cd backend

# 1) Bring up the full stack (base services + auth overlay)
docker compose -f compose.yaml -f compose.auth.yaml up -d --build

# 2) Apply DB migrations and seed (creates the approved demo user
#    demo@oqtopus.local). These talk to the DB on localhost:3306.
make migrate-up
make seed
```

Wait ~30–60s for Keycloak to import the realm and OpenLDAP to seed
(OpenLDAP runs under amd64 emulation on Apple Silicon, so first boot is slow).

## Demo credentials

| What | Value |
| --- | --- |
| LDAP demo user | `demo` / `demopassword` (email `demo@oqtopus.local`) |
| Keycloak admin console | http://localhost:8081  (admin / admin) |
| oauth2-proxy (app entry) | http://localhost:4180 |
| User API (direct) | http://localhost:8080 |

## Try it — browser (full flow)

Open <http://localhost:4180/users/me> in a browser. You'll be redirected to
Keycloak, log in as `demo` / `demopassword`, and land back on the User API
response for the authenticated user — e.g.

```json
{"id":"demo@oqtopus.local","email":"demo@oqtopus.local","name":"OQTOPUS Demo User", ...}
```

## Try it — scripted (no browser)

This exercises exactly the API-side auth seam (OIDC verify + authorization),
getting a token straight from Keycloak via the password grant:

```bash
# 1) Get an ID token for the LDAP-backed demo user
ID_TOKEN=$(curl -s \
  -d grant_type=password \
  -d client_id=oqtopus-oauth2-proxy \
  -d client_secret=oauth2-proxy-secret \
  -d username=demo -d password=demopassword \
  -d scope=openid \
  http://localhost:8081/realms/oqtopus/protocol/openid-connect/token \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id_token"])')

# 2) Call the User API with the token
curl -s -H "Authorization: Bearer $ID_TOKEN" http://localhost:8080/users/me | python3 -m json.tool
curl -s -H "Authorization: Bearer $ID_TOKEN" http://localhost:8080/devices | python3 -m json.tool

# 3) Negative checks
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/users/me                       # 401 (no token)
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer bad.jwt" http://localhost:8080/users/me  # 401
```

> Note: `/users/me` also exposes an AWS-CloudTrail-backed *login history*; that
> feature is disabled in this demo (`LOGIN_HISTORY_ENABLED=false`) because it
> requires AWS. Everything else (identity + authorization) is fully local.

## How the pieces are configured

- `compose.auth.yaml` — the overlay: `openldap`, `keycloak`, `oauth2-proxy`, and
  the `user-api` override (`AUTH_MODE=oidc` + `OIDC_*`).
- `auth-demo/ldap/demo.ldif` — the seed directory entry (uid=demo, mail=…).
- `auth-demo/keycloak/realm.json` — realm `oqtopus`, the `oqtopus-oauth2-proxy`
  client, and the LDAP user-federation provider + attribute mappers.

### The Keycloak-in-Docker hostname split

Tokens must carry a stable `iss` that both the browser and the in-network
services agree on. Keycloak is pinned to `KC_HOSTNAME=http://localhost:8081`
(so `iss` and browser redirects use `localhost:8081`), while
`KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true` lets in-network services still reach it at
`http://keycloak:8080`. Hence:

- `OIDC_ISSUER = http://localhost:8081/realms/oqtopus` (matches the token `iss`)
- `OIDC_JWKS_URL = http://keycloak:8080/realms/oqtopus/.../certs` (reachable from user-api)

## Mapping back to production / a real deployment

- To point at a **different OIDC provider** (incl. Cognito), change only the
  `OIDC_ISSUER` / `OIDC_JWKS_URL` / `OIDC_AUDIENCE` / `OIDC_USERNAME_CLAIM` env
  vars — no code changes. The verification in `common/auth/oidc.py` is generic.
- The AWS production path is untouched: with `AUTH_MODE` unset (and not
  `ENV=local`) the API still reads the API Gateway Lambda-authorizer context.
- **Machine clients** (`quri-parts-oqtopus`, `q-api-token`) are out of scope for
  this browser-OIDC demo; that path stays in-app (DB-backed API tokens) and can
  be wired so oauth2-proxy skips requests carrying `Q-API-Token`.

## Stop / reset

```bash
docker compose -f compose.yaml -f compose.auth.yaml down          # stop
docker compose -f compose.yaml -f compose.auth.yaml down -v       # + wipe volumes
```
