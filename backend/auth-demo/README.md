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
# 1) Get an access token for the LDAP-backed demo user
ACCESS_TOKEN=$(curl -s \
  -d grant_type=password \
  -d client_id=oqtopus-oauth2-proxy \
  -d client_secret=oauth2-proxy-secret \
  -d username=demo -d password=demopassword \
  -d scope=openid \
  http://localhost:8081/realms/oqtopus/protocol/openid-connect/token \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2) Call the User API with the token
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/users/me | python3 -m json.tool
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8080/devices | python3 -m json.tool

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
- **Machine clients** (`oqtopus-client` / `quri-parts-oqtopus`, authenticating
  with a `Q-API-Token`) use the same User API but a **different entry point** —
  they bypass oauth2-proxy and the token is verified in-app. See
  [Machine clients — Q-API-Token (CLI)](#machine-clients--q-api-token-cli) below.

---

# Machine clients — Q-API-Token (CLI)

Programmatic clients (`oqtopus-client`, `quri-parts-oqtopus`) do **not** use OIDC.
They authenticate to the User API with a static `Q-API-Token: <id>.<secret>`
header. In AWS this token is checked by the API Gateway Lambda authorizer; on-prem
the **same check runs in-app** (`common/auth/client.py`: Argon2 hash, expiry, and
`userstatus == approved`). This section covers local development and the rules for
a real deployment.

## 1. Normal local startup (`make up`) — authentication is **bypassed**

```bash
cd backend
make up        # docker compose up -d + migrate + seed + init storage
```

The default `compose.yaml` runs the User API with `ENV=local`, which resolves
every request to a **fixed developer identity** (`admin-email`) and **never runs
the Q-API-Token check**. This is the fast path for day-to-day work on handlers;
it tells you nothing about authentication.

| | `make up` (default) | Auth overlay (below) |
| --- | --- | --- |
| `ENV` | `local` | `local` (DB/MinIO wiring only) |
| `AUTH_MODE` | *(unset → `local`)* | `oidc` |
| Request identity | fixed `admin-email`, no checks | OIDC Bearer **or** `Q-API-Token`, verified |
| Q-API-Token verified? | **No** | **Yes** (`client.py`) |

## 2. Enabling Q-API-Token verification (auth overlay)

Bring the stack up with the auth overlay, which switches the User API to
`AUTH_MODE=oidc`. In this mode the in-app `AuthMiddleware` dispatches on the
request headers: a `Q-API-Token` header → the DB-backed token verifier; otherwise
an `Authorization: Bearer` → OIDC JWT verification.

```bash
cd backend
docker compose -f compose.yaml -f compose.auth.yaml up -d --build
make migrate-up && make seed      # if not already seeded (creates demo@oqtopus.local, approved)
```

`ENV` stays `local` (so DB/MinIO wiring is unchanged); `AUTH_MODE=oidc` is the
independent switch that turns real authentication on. Keycloak comes up with the
overlay too — it is only needed to *issue* a token (step 4); verifying a
`Q-API-Token` itself hits the DB, not Keycloak.

## 3. Pointing `oqtopus-client` at the User API (direct, **not** via the BFF)

The CLI connects **straight to the User API**, bypassing oauth2-proxy / nginx:

```bash
export OQTOPUS_URL=http://localhost:8080          # User API, direct
export OQTOPUS_API_TOKEN='<id>.<secret>'          # from step 4
```

**Why not the BFF (`:4200/api`)?** In the BFF, nginx guards `/api/*` with an
`auth_request` subrequest to oauth2-proxy. A CLI request carries no oauth2-proxy
**session cookie**, so oauth2-proxy returns 401 and nginx never forwards the
request to the User API — the `Q-API-Token` is never even looked at. The token
path must therefore terminate at the User API directly (locally `:8080`; in a
real deployment, a dedicated HTTPS host — see §6).

## 4. Issuing an API token (OIDC browser session only)

API tokens are minted from an **OIDC-authenticated** session. A client that is
already authenticated **with a Q-API-Token cannot mint a new one** — `POST
/api-token` returns **403** in that case (so a leaked token cannot renew itself
indefinitely). Issuance is therefore a web-console / browser responsibility:

```text
browser OIDC login  →  POST /api-token  →  set <id>.<secret> on the client
                    →  oqtopus-client calls the User API directly
```

Scripted end-to-end (no browser), against the auth overlay from §2:

```bash
# 1) Get an OAuth2 access token for the approved demo user (Keycloak password grant)
ACCESS_TOKEN=$(curl -s \
  -d grant_type=password \
  -d client_id=oqtopus-oauth2-proxy -d client_secret=oauth2-proxy-secret \
  -d username=demo -d password=demopassword -d scope=openid \
  http://localhost:8081/realms/oqtopus/protocol/openid-connect/token \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# 2) Issue an API token (OIDC Bearer) and assemble "<id>.<secret>"
TOKEN=$(curl -s -X POST -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://localhost:8080/api-token \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["api_token_id"] + "." + d["api_token_secret"])')
echo "Q-API-Token: $TOKEN"

# 3) Use the Q-API-Token (this is what oqtopus-client sends)
curl -s -H "q-api-token: $TOKEN" http://localhost:8080/devices | python3 -m json.tool
```

### Connectivity check (expected status codes)

```bash
# 200 — valid Q-API-Token
curl -s -o /dev/null -w 'token OK:        %{http_code}\n' -H "q-api-token: $TOKEN" http://localhost:8080/devices
# 401 — bad/malformed token (note: NO "WWW-Authenticate: Bearer" on this path)
curl -s -o /dev/null -w 'bad token:       %{http_code}\n' -H "q-api-token: nope.nope" http://localhost:8080/devices
# 401 — no credentials at all
curl -s -o /dev/null -w 'no creds:        %{http_code}\n' http://localhost:8080/devices
# 403 — a Q-API-Token caller may NOT mint a new token
curl -s -o /dev/null -w 'self-reissue:    %{http_code}\n' -X POST -H "q-api-token: $TOKEN" http://localhost:8080/api-token
```

## 5. `oqtopus-auth` dependency

`oqtopus-auth` is consumed from **PyPI**, pinned in `uv.lock` (`>=1.0.0,<2`). No
sibling checkout, BuildKit additional context, or `COPY --from=oqtopus_auth` is
needed — `uv sync --frozen` resolves it like any other dependency during the
Docker build.

For **local co-development** against a checkout of `oqtopus-auth` (e.g. to test an
unreleased change), add a path override to `pyproject.toml` and re-lock:

```toml
[tool.uv.sources]
oqtopus-auth = { path = "../oqtopus-auth", editable = true }
```

(Do not commit that override; the committed build uses the published package.)

## 6. Production / shared-environment requirements

The User API direct path (the CLI entry point) must, at minimum:

- **Terminate TLS (HTTPS).** Q-API-Tokens are bearer credentials.
- **Set `AUTH_MODE=oidc` explicitly.** Do not rely on defaults.
- **Rate-limit** the direct host. The Argon2 verify is intentionally expensive;
  cap it at the edge (the app also bounds concurrency via `AUTH_MAX_CONCURRENCY`).
- **Never create a path that bypasses the FastAPI `AuthMiddleware`.** Every route
  to the User API must pass through it.
- **Separate the two front doors by purpose:** a browser **BFF host** (nginx +
  oauth2-proxy, OIDC, same-origin `/api`) and a **direct User-API host** for CLI
  `Q-API-Token` traffic. Mirrors the AWS split (SPA host vs API custom domain);
  the direct host replaces API Gateway + Lambda authorizer with the in-app check.

---

# Frontend (SPA) via BFF

The sections above authenticate the **API**. This part puts the **oqtopus-frontend
SPA** in front of it using the BFF (Backend-For-Frontend) pattern: a single-origin
reverse proxy (nginx) fronts the SPA and the API, and oauth2-proxy owns the entire
login lifecycle. **The SPA holds no tokens and is auth-unaware** — it only asks
"who am I?" via `/oauth2/userinfo` and hands off to the proxy to log in.

```
Browser ─cookie─▶ nginx :4200 ─┬─ /          → SPA static (oqtopus-frontend/dist)
                               ├─ /oauth2/*  → oauth2-proxy → Keycloak :8081 → LDAP
                               └─ /api/*     → (auth_request) → user-api :8080
                                              nginx injects the id_token oauth2-proxy
                                              returns, and strips the /api prefix.
```

## Frontend changes — pluggable auth drivers (`cognito` | `proxy`)

Auth is a **pluggable driver** selected by `VITE_APP_AUTH_MODE`; the rest of the
app depends only on the driver contract, never on a specific identity provider.

```
src/auth/
  contract.ts      # UseAuth (the driver contract), Result, AuthContext
  hook.ts          # useAuth()
  Provider.tsx     # registry: lazy-loads the driver for AUTH_MODE (code-split)
  drivers/
    cognito.tsx    # CognitoAuthProvider — isolates aws-amplify
    proxy.tsx      # ProxyAuthProvider — BFF: userinfo/redirect only, no tokens
```

- The registry picks the driver from a **build-time constant**, so the unused
  driver (and its deps) is dead-code-eliminated: a `proxy` build ships **no
  aws-amplify/Cognito code**, a `cognito` build ships no proxy driver. Set
  `VITE_APP_AUTH_MODE` explicitly at build time for a fully-split bundle.
- **proxy driver**: login state from `/oauth2/userinfo`; `signIn`/`signOut` are
  redirects to `/oauth2/start` / `/logout`; sign-up / MFA / password-reset are
  delegated to Keycloak (see below). No `Authorization` header — the proxy
  injects the token. API base defaults to same-origin `/api`.
- **cognito driver**: the original Amplify/Cognito flows, unchanged.
- Adding a new backend = add `drivers/<name>.tsx` returning a `UseAuth` and a
  branch in `Provider.tsx`. `src/env/index.ts` also exposes `AUTH_MODE`.

## Run it

```bash
# 1) Build the SPA in proxy mode (from the frontend repo)
cd ../../oqtopus-frontend        # adjust to your checkout
bun install
VITE_APP_AUTH_MODE=proxy \
  VITE_APP_ACCOUNT_CONSOLE_URL=http://localhost:8081/realms/oqtopus/account/ \
  bun run build

# 2) Bring up the full stack incl. nginx + SPA (from backend/)
cd -                             # back to backend/
docker compose -f compose.yaml -f compose.auth.yaml -f compose.frontend.yaml up -d --build
make migrate-up && make seed     # if not already seeded
```

Then open <http://localhost:4200/dashboard> in a browser:

1. You're redirected to Keycloak and log in as **`demo` / `demopassword`** (LDAP).
2. **First login forces TOTP (MFA) enrollment** — scan the QR with an authenticator
   app (Google Authenticator, etc.) and enter the 6-digit code. Subsequent logins
   require that code.
3. You land back in the SPA, authenticated; its API calls flow through nginx →
   user-api with the proxy-injected token.

MFA is enforced by Keycloak's realm (`requiredActions: CONFIGURE_TOTP`,
`defaultAction: true` in `auth-demo/keycloak/realm.json`) — no MFA code lives in
the SPA or the backend anymore.

### Password change & MFA reset (proxy mode)

These are delegated to Keycloak's self-service **Account Console** rather than
reimplemented in the SPA. In proxy mode, **Settings → Account** shows a
"Change password in Keycloak" button and **Settings → Security** shows a
"Manage MFA in Keycloak" button; both open
`…/realms/oqtopus/account/#/security/signing-in` (via `VITE_APP_ACCOUNT_CONSOLE_URL`),
where the user can change their password and add/remove their OTP authenticator
(= MFA reset). The existing Keycloak SSO session is reused, so no re-login is
needed. Logout uses RP-initiated logout (`/logout` → Keycloak end-session with
`id_token_hint` captured server-side by nginx+njs) so no confirmation prompt
appears and both the proxy and IdP sessions end.

## Configuration files

- `compose.frontend.yaml` — adds `nginx`, switches oauth2-proxy to nginx
  `auth_request` mode (`--set-authorization-header`), and mounts the SPA `dist/`.
- `auth-demo/nginx/nginx.conf` — the single-origin front door (static + `/oauth2`
  + `auth_request`-gated `/api` with prefix strip and Bearer injection).

## Mapping to production

- Any single-origin reverse proxy (nginx/ALB/CloudFront+Lambda@Edge, or a custom
  BFF) can play nginx's role; oauth2-proxy stays the auth layer. The SPA build is
  provider-agnostic — only `VITE_APP_AUTH_MODE` and the proxy config change.
- The **Cognito/AWS** path is fully preserved: build without `VITE_APP_AUTH_MODE`
  (or `=cognito`) and the SPA keeps its Amplify login, MFA and signup screens.
- Login/sign-up/MFA/password UI is served by **Keycloak** (themeable — see
  Keycloak themes / `keycloakify` to reproduce the brand). The SPA's
  `src/pages/auth/**` screens are used only in `cognito` mode.

## Stop / reset

```bash
# API-only demo
docker compose -f compose.yaml -f compose.auth.yaml down            # stop
docker compose -f compose.yaml -f compose.auth.yaml down -v         # + wipe volumes

# Full frontend BFF demo (add -f compose.frontend.yaml)
docker compose -f compose.yaml -f compose.auth.yaml -f compose.frontend.yaml down
```

> Recreating the `keycloak` container resets its in-memory dev DB, so the demo
> user must re-enroll TOTP on the next login (expected for this ephemeral demo).
