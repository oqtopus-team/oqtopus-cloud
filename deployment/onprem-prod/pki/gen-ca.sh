#!/usr/bin/env bash
# Internal CA + leaf certificates for the on-prem OQTOPUS auth stack.
#
# Run this on the ADMIN TERMINAL (not the production server). The Root CA
# private key (out/ca/ca.key) must stay here, offline -- only the issued leaf
# certificates/keys and the CA *certificate* (ca.crt, for truststores) are
# copied to the server. See deployment/onprem-prod/README.md.
#
# Usage:
#   ./gen-ca.sh [BASE_DOMAIN]      # default: oqtopus.internal
#
# Produces (idempotent; re-runs reuse an existing CA):
#   out/ca/ca.crt  out/ca/ca.key
#   out/certs/<svc>.crt  out/certs/<svc>.key   for svc in auth app ldap db
#
# Each leaf lists SANs for: its FQDN (<svc>.<BASE_DOMAIN>), its docker service
# name (keycloak/nginx/openldap/db), and localhost/127.0.0.1 so the same cert
# works for in-network TLS and for local browser testing via /etc/hosts.
set -euo pipefail

BASE_DOMAIN="${1:-oqtopus.internal}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${HERE}/out"
CA_DIR="${OUT}/ca"
CERT_DIR="${OUT}/certs"
DAYS_CA=3650
DAYS_LEAF=825

mkdir -p "${CA_DIR}" "${CERT_DIR}"
chmod 700 "${OUT}" "${CA_DIR}" "${CERT_DIR}"

# --- Root CA (reused if present) -------------------------------------------
if [[ ! -f "${CA_DIR}/ca.key" ]]; then
  echo "==> creating internal Root CA"
  openssl genrsa -out "${CA_DIR}/ca.key" 4096
  chmod 600 "${CA_DIR}/ca.key"
  openssl req -x509 -new -nodes -key "${CA_DIR}/ca.key" -sha256 -days "${DAYS_CA}" \
    -subj "/O=OQTOPUS/OU=on-prem/CN=OQTOPUS Internal Root CA" \
    -out "${CA_DIR}/ca.crt"
else
  echo "==> reusing existing Root CA at ${CA_DIR}/ca.crt"
fi

# svc -> docker service name (extra SAN). Space-separated "svc:host" pairs
# (no associative arrays, for bash 3.2 compatibility on macOS admin terminals).
SVC_HOSTS="auth:keycloak app:nginx admin:nginx-admin ldap:openldap db:db"

issue_leaf() {
  local svc="$1" docker_host="$2"
  local fqdn="${svc}.${BASE_DOMAIN}"
  if [[ -f "${CERT_DIR}/${svc}.crt" && -f "${CERT_DIR}/${svc}.key" ]]; then
    echo "==> reusing existing leaf: ${fqdn}"
    return
  fi
  echo "==> issuing leaf: ${fqdn} (SAN: ${docker_host}, localhost)"
  local cnf; cnf="$(mktemp)"
  cat >"${cnf}" <<EOF
[req]
distinguished_name = dn
req_extensions = v3_req
prompt = no
[dn]
O = OQTOPUS
OU = on-prem
CN = ${fqdn}
[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt
[alt]
DNS.1 = ${fqdn}
DNS.2 = ${docker_host}
DNS.3 = localhost
IP.1  = 127.0.0.1
EOF
  openssl genrsa -out "${CERT_DIR}/${svc}.key" 2048
  chmod 600 "${CERT_DIR}/${svc}.key"
  openssl req -new -key "${CERT_DIR}/${svc}.key" -out "${CERT_DIR}/${svc}.csr" \
    -config "${cnf}"
  openssl x509 -req -in "${CERT_DIR}/${svc}.csr" \
    -CA "${CA_DIR}/ca.crt" -CAkey "${CA_DIR}/ca.key" -CAcreateserial \
    -out "${CERT_DIR}/${svc}.crt" -days "${DAYS_LEAF}" -sha256 \
    -extfile "${cnf}" -extensions v3_req
  rm -f "${CERT_DIR}/${svc}.csr" "${cnf}"
}

for pair in ${SVC_HOSTS}; do
  issue_leaf "${pair%%:*}" "${pair##*:}"
done

echo
echo "Done. Base domain: ${BASE_DOMAIN}"
echo "CA cert (distribute to truststores/browsers): ${CA_DIR}/ca.crt"
echo "Keep ${CA_DIR}/ca.key OFFLINE on this admin terminal; do NOT copy it to the server."
