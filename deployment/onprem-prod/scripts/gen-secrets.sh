#!/usr/bin/env bash
# Generate the on-prem secret files injected at runtime (never committed).
#
# Writes deployment/onprem-prod/secrets/ with 0600 files, one secret per file,
# plus the app DB credential JSON consumed via DB_SECRET_FILE. Re-running keeps
# existing files (idempotent) so rotation is explicit.
#
# Secret files (all 0600):
#   mysql_root_password         MySQL root (bootstrap only)
#   db_app_password             MySQL app user password
#   db_app_secret.json          {"username","password"} for DB_SECRET_FILE
#   keycloak_db_password         MySQL user password for the Keycloak schema
#   keycloak_admin_password      Keycloak bootstrap admin password
#   ldap_admin_password          OpenLDAP root (bootstrap only)
#   ldap_bind_password           Dedicated Keycloak->LDAP service bind account
#   oauth2_proxy_cookie_secret   user BFF cookie secret (32 bytes, base64)
#   oauth2_proxy_admin_cookie_secret  admin BFF cookie secret
#   oauth2_proxy_client_secret   Keycloak client secret (user BFF)
#   oauth2_proxy_admin_client_secret  Keycloak client secret (admin BFF)
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SEC="${HERE}/secrets"
mkdir -p "${SEC}"
chmod 700 "${SEC}"

DB_USER="${DB_APP_USERNAME:-oqtopus}"

w() {  # w <file> <generator-cmd...>  -- write only if absent, 0600
  local f="${SEC}/$1"; shift
  if [[ -f "${f}" ]]; then echo "keep  ${f}"; return; fi
  "$@" >"${f}"
  chmod 600 "${f}"
  echo "write ${f}"
}

rand_b64() { openssl rand -base64 "${1:-24}" | tr -d '\n'; }
# oauth2-proxy v7.6.0 decodes the cookie secret as Base64URL, so emit 32 raw
# bytes as URL-safe base64 (no '+' '/' '=') -- a standard-base64 '+'/'/' would
# fail to decode and could stop the proxy from starting.
rand_cookie() { openssl rand -base64 32 | tr '+/' '-_' | tr -d '=\n'; }

w mysql_root_password            rand_b64 24
w db_app_password                rand_b64 24
w keycloak_db_password           rand_b64 24
w keycloak_admin_password        rand_b64 24
w ldap_admin_password            rand_b64 24
w ldap_bind_password             rand_b64 24
w ldap_ops_password              rand_b64 24
w oauth2_proxy_cookie_secret        rand_cookie
w oauth2_proxy_admin_cookie_secret  rand_cookie
w oauth2_proxy_client_secret        rand_b64 24
w oauth2_proxy_admin_client_secret  rand_b64 24

# oauth2-proxy reads the cookie secret from a --config file (there is no
# --cookie-secret-file flag), so the standard distroless image needs no shell.
# The client secret is passed with --client-secret-file. Generate the config
# files holding only cookie_secret.
gen_o2p_cfg() {  # gen_o2p_cfg <cfg-name> <cookie-secret-file>
  local cfg="${SEC}/$1" src="${SEC}/$2"
  if [[ -f "${cfg}" ]]; then echo "keep  ${cfg}"; return; fi
  printf 'cookie_secret = "%s"\n' "$(cat "${src}")" >"${cfg}"
  chmod 600 "${cfg}"
  echo "write ${cfg}"
}
gen_o2p_cfg oauth2-proxy.cfg        oauth2_proxy_cookie_secret
gen_o2p_cfg oauth2-proxy-admin.cfg  oauth2_proxy_admin_cookie_secret

# SeaweedFS object-store credentials (no insecure defaults in the manifest):
# a KEY=VALUE env file shared by seaweedfs and the APIs.
if [[ ! -f "${SEC}/seaweedfs.env" ]]; then
  swuser="oqtopus"
  swpass="$(rand_b64 24)"
  {
    echo "STORAGE_SEAWEEDFS_USERNAME=${swuser}"
    echo "STORAGE_SEAWEEDFS_PASSWORD=${swpass}"
    echo "AWS_ACCESS_KEY_ID=${swuser}"
    echo "AWS_SECRET_ACCESS_KEY=${swpass}"
  } >"${SEC}/seaweedfs.env"
  chmod 600 "${SEC}/seaweedfs.env"
  echo "write ${SEC}/seaweedfs.env"
else
  echo "keep  ${SEC}/seaweedfs.env"
fi

# LDAP service-bind accounts LDIF (passwords injected, never committed). The
# dedicated Keycloak (read) and ops (write) bind accounts' userPassword must
# equal the ldap_bind_password / ldap_ops_password secrets, so seed their
# hashes here. {SSHA} is used for these machine BIND accounts; end-user
# passwords are set by the server via the Password Modify ExtOp under the
# strong-hash cn=config (see ldap/config/).
if [[ ! -f "${SEC}/ldap-bind-accounts.ldif" ]]; then
  python3 - "${SEC}/ldap_bind_password" "${SEC}/ldap_ops_password" "${OQTOPUS_BASE_DOMAIN:-oqtopus.internal}" >"${SEC}/ldap-bind-accounts.ldif" <<'PY'
import base64, hashlib, os, sys
def ssha(pw: str) -> str:
    salt = os.urandom(8)
    h = hashlib.sha1(pw.encode() + salt).digest()
    return "{SSHA}" + base64.b64encode(h + salt).decode()
kc = open(sys.argv[1]).read().strip()
ops = open(sys.argv[2]).read().strip()
dc = ",".join(f"dc={p}" for p in sys.argv[3].split("."))
print(f"""dn: cn=keycloak,ou=services,{dc}
objectClass: organizationalRole
objectClass: simpleSecurityObject
cn: keycloak
description: Keycloak LDAP federation bind (read-only)
userPassword: {ssha(kc)}

dn: cn=ops,ou=services,{dc}
objectClass: organizationalRole
objectClass: simpleSecurityObject
cn: ops
description: Ops CLI bind (writes ou=people / ou=groups)
userPassword: {ssha(ops)}
""")
PY
  chmod 600 "${SEC}/ldap-bind-accounts.ldif"
  echo "write ${SEC}/ldap-bind-accounts.ldif"
else
  echo "keep  ${SEC}/ldap-bind-accounts.ldif"
fi

# App DB credential JSON (consumed by DB_CREDENTIAL_SOURCE=file). Keep its
# password in sync with db_app_password.
if [[ ! -f "${SEC}/db_app_secret.json" ]]; then
  python3 - "${SEC}/db_app_password" "${DB_USER}" >"${SEC}/db_app_secret.json" <<'PY'
import json, sys
pw = open(sys.argv[1]).read().strip()
print(json.dumps({"username": sys.argv[2], "password": pw}))
PY
  chmod 600 "${SEC}/db_app_secret.json"
  echo "write ${SEC}/db_app_secret.json"
else
  echo "keep  ${SEC}/db_app_secret.json"
fi

echo
echo "Done. ${SEC} (0600 files). These are injected at runtime; never commit them."
