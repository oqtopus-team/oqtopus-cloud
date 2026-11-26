#!/usr/bin/env bash
# Apply the OpenLDAP cn=config (ppolicy overlay, strong hash, ACLs) and the
# default password-policy entry, then VERIFY the resulting state. Run AFTER
# `openldap` is up and BEFORE starting Keycloak / testing browser login -- a
# failure here aborts (non-zero exit) so the auth bring-up stops.
#
# All changes go over the local ldapi socket with EXTERNAL auth (no password on
# the command line). Idempotent: a change that already exists (ldap rc 20/68)
# is accepted, but the final verification must still confirm every expected
# piece, so a partial apply cannot pass.
#
#   ./scripts/apply-ldap-config.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Target the same Compose project as the bring-up (exec must not guess it).
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-oqtopus-onprem}"
dc() { docker compose -f compose.yaml "$@"; }
ldctl() { dc exec -T openldap "$@"; }

modify() {  # modify <description> <ldif-file> <add|modify>
  local desc="$1" file="$2" op="$3"
  echo "==> ${desc}"
  local rc=0
  if [[ "${op}" == "add" ]]; then
    ldctl ldapadd -Y EXTERNAL -H ldapi:/// < "${file}" || rc=$?
  else
    ldctl ldapmodify -Y EXTERNAL -H ldapi:/// < "${file}" || rc=$?
  fi
  # 0 ok; 68 = entry already exists; 20 = attribute/value exists -> idempotent.
  if [[ "${rc}" -ne 0 && "${rc}" -ne 68 && "${rc}" -ne 20 ]]; then
    echo "ERROR: ${desc} failed (ldap rc=${rc})" >&2
    exit 1
  fi
}

# cn=config: modules, olcPasswordHash, ppolicy overlay, ACLs (one modify stream).
modify "cn=config: modules / olcPasswordHash / ppolicy overlay / ACLs" \
  ldap/config/10-ppolicy-acl-hash.ldif modify
# Default password-policy entry (pwdMustChange) in the data tree, written by the
# local ldapi root (ACL grants it write to ou=policies only).
modify "data: default password policy entry (pwdMustChange)" \
  ldap/config/20-default-policy.ldif add

echo "==> verifying applied state"
expect() {  # expect <description> <base> <scope: base|sub> <filter> <needle>
  local desc="$1" base="$2" scope="$3" filter="$4" needle="$5" out
  # Capture first (don't pipe into grep -q): with `set -o pipefail`, grep -q's
  # early exit sends SIGPIPE to ldapsearch and would fail the pipeline.
  out="$(ldctl ldapsearch -Y EXTERNAL -H ldapi:/// -LLL -s "${scope}" -b "${base}" "${filter}" 2>/dev/null || true)"
  if ! printf '%s' "${out}" | grep -qiF "${needle}"; then
    echo "ERROR: verification failed -- ${desc}" >&2
    exit 1
  fi
  echo "  ok: ${desc}"
}

expect "strong password hash {PBKDF2-SHA512}" \
  "olcDatabase={-1}frontend,cn=config" base "(objectClass=*)" "{PBKDF2-SHA512}"
# The overlay gets an ordering index in its DN (e.g. {2}ppolicy); match by the
# policy-default attribute under the data database instead of a fixed DN.
expect "ppolicy overlay forces the default policy" \
  "olcDatabase={1}mdb,cn=config" sub "(olcPPolicyDefault=*)" \
  "olcPPolicyDefault: cn=default,ou=policies,dc=oqtopus,dc=internal"
expect "default policy entry forces pwdMustChange" \
  "cn=default,ou=policies,dc=oqtopus,dc=internal" base "(objectClass=*)" "pwdMustChange: TRUE"

echo "OK: LDAP cn=config + default policy applied and verified."
