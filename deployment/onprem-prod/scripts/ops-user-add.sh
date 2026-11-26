#!/usr/bin/env bash
# ops-user-add.sh -- create an end-user directory entry and set a one-time
# temporary password, over LDAPS, using the dedicated `ops` bind account.
#
# ppolicy (pwdMustChange on the default policy) marks the entry pwdReset because
# the password is set by someone other than the user, so Keycloak (with
# "Enable LDAP password policy") forces a password change at the first browser
# login. The server stores the password as {PBKDF2-SHA512} via the Password
# Modify extended operation -- no hash is ever computed client-side.
#
#   COMPOSE_PROJECT_NAME=oqtopus-onprem \
#     ./scripts/ops-user-add.sh <uid> <email> ["Display Name"]
#
# The temporary password is generated here and printed ONCE to the operator; it
# reaches the directory only over LDAPS. The ops bind password is read from the
# secret file and handed to the client via a transient in-container file
# (mode 0600), never on the command line.
set -euo pipefail
cd "$(dirname "$0")/.."
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-oqtopus-onprem}"

[[ $# -ge 2 ]] || { echo "usage: $0 <uid> <email> [display-name]" >&2; exit 2; }
NEWUID="$1"; MAIL="$2"; DISPLAY_NAME="${3:-$1}"
BASE="dc=oqtopus,dc=internal"
OPS_DN="cn=ops,ou=services,${BASE}"
USER_DN="uid=${NEWUID},ou=people,${BASE}"
CACERT="/container/service/slapd/assets/certs/ca.crt"

[[ -f secrets/ldap_ops_password ]] || { echo "ERROR: secrets/ldap_ops_password missing (run gen-secrets.sh)" >&2; exit 1; }
OPS_PW="$(cat secrets/ldap_ops_password)"

# One-time temporary password: 16 shell/URL-safe chars.
TMPPW="$(openssl rand -base64 18 | tr '+/' 'Aa' | tr -d '=' | cut -c1-16)"

# Phase 1 identity: mail == the user id, so the same LDAP user re-logging in
# yields the same Keycloak `sub` (OIDC_IDENTITY_RESOLVER=cognito_sub).
LDIF="dn: ${USER_DN}
objectClass: inetOrgPerson
objectClass: organizationalPerson
objectClass: person
uid: ${NEWUID}
cn: ${DISPLAY_NAME}
sn: ${DISPLAY_NAME}
mail: ${MAIL}
"

# `docker compose exec -e VAR` only forwards EXPORTED environment variables.
export OPS_PW LDIF OPS_DN USER_DN TMPPW CACERT
docker compose -f compose.yaml exec -T \
  -e OPS_PW -e LDIF -e OPS_DN -e USER_DN -e TMPPW -e CACERT \
  openldap sh -c '
    set -e
    export LDAPTLS_CACERT="$CACERT"
    pf="$(mktemp)"; lf="$(mktemp)"; chmod 600 "$pf" "$lf"
    trap "rm -f \"$pf\" \"$lf\"" EXIT
    printf "%s" "$OPS_PW"   > "$pf"
    printf "%s\n" "$LDIF"   > "$lf"
    ldapadd    -x -H ldaps://openldap:636 -D "$OPS_DN" -y "$pf" -f "$lf"
    ldappasswd -x -H ldaps://openldap:636 -D "$OPS_DN" -y "$pf" -s "$TMPPW" "$USER_DN"
    # Force the change at first login: mark the entry pwdReset so Keycloak (with
    # "Enable LDAP password policy") presents UPDATE_PASSWORD. The ppolicy
    # overlay does not set this automatically for the Password Modify ExtOp, so
    # set it explicitly as the ops bind (which has write access to ou=people).
    ldapmodify -x -H ldaps://openldap:636 -D "$OPS_DN" -y "$pf" <<LDIF
dn: $USER_DN
changetype: modify
replace: pwdReset
pwdReset: TRUE
LDIF
  '

cat <<EOF

Created ${USER_DN}
  email (Phase 1 user id): ${MAIL}
  Temporary password (deliver over a secure channel; change is forced at first
  login, and the user cannot change their email from the account console):

    ${TMPPW}

EOF
