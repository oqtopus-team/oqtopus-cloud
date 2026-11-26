#!/usr/bin/env bash
# S1 CI guard (implementation plan): fail if any forbidden demo/insecure setting
# leaks into the on-prem PRODUCTION manifest roots.
#
# Demo configs (backend/*.yaml, backend/auth-demo/) legitimately use these
# settings and are intentionally NOT scanned -- this guard only looks under the
# production roots. Production manifests are created after S0 (basis ADR); until
# then the production root may be empty and the guard passes, but the check is
# wired and ready.
#
# Usage:
#   scripts/ci/onprem_prod_guard.sh            # scan $PROD_ROOTS (default below)
#   scripts/ci/onprem_prod_guard.sh --selftest # scan the known-bad fixture; MUST find violations
#
# Env:
#   PROD_ROOTS  space-separated production roots to scan (default: deployment/onprem-prod)
#   PATTERNS    path to the forbidden-patterns file
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PATTERNS="${PATTERNS:-$HERE/onprem_prod_forbidden_patterns.txt}"
PROD_ROOTS="${PROD_ROOTS:-deployment/onprem-prod}"

selftest=0
if [ "${1:-}" = "--selftest" ]; then
  selftest=1
  PROD_ROOTS="$HERE/testdata"
fi

if [ ! -f "$PATTERNS" ]; then
  echo "guard: patterns file not found: $PATTERNS" >&2
  exit 2
fi

# Collect files to scan (config-ish text), excluding VCS and the guard's own testdata
# unless we are in selftest mode.
collect_files() {
  local root="$1"
  [ -e "$root" ] || return 0
  find "$root" -type f \
    \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' -o -name '*.env' \
       -o -name '*.conf' -o -name '*.tf' -o -name '*.tfvars' -o -name '*.sh' \
       -o -name '*.properties' -o -name '*.ldif' -o -name 'Dockerfile*' \) \
    2>/dev/null
}

files=""
for root in $PROD_ROOTS; do
  found="$(collect_files "$root")"
  [ -n "$found" ] && files="$files$found"$'\n'
done
files="$(printf '%s' "$files" | sed '/^$/d')"

if [ -z "$files" ]; then
  if [ "$selftest" -eq 1 ]; then
    echo "guard selftest: no fixture files found under $PROD_ROOTS" >&2
    exit 2
  fi
  echo "guard: no production manifests under: $PROD_ROOTS (nothing to scan yet) -- OK"
  exit 0
fi

violations=0
while IFS=$'\t' read -r regex desc; do
  case "$regex" in ''|\#*) continue ;; esac
  # grep across all target files; -I skip binary, -n line numbers, -E ERE
  if matches="$(printf '%s\n' "$files" | xargs -r grep -InE -- "$regex" 2>/dev/null)"; then
    if [ -n "$matches" ]; then
      violations=$((violations + 1))
      echo "FORBIDDEN: $desc"
      echo "  pattern: $regex"
      printf '%s\n' "$matches" | sed 's/^/    /'
      echo
    fi
  fi
done < "$PATTERNS"

if [ "$selftest" -eq 1 ]; then
  if [ "$violations" -gt 0 ]; then
    echo "guard selftest: OK -- detected $violations forbidden pattern(s) in the fixture."
    exit 0
  fi
  echo "guard selftest: FAILED -- the known-bad fixture produced no findings." >&2
  exit 1
fi

if [ "$violations" -gt 0 ]; then
  echo "guard: $violations forbidden setting group(s) found in production roots ($PROD_ROOTS)." >&2
  exit 1
fi
echo "guard: no forbidden settings found in: $PROD_ROOTS -- OK"
exit 0
