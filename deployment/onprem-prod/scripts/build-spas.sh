#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 ]]; then
    echo "Usage: $0 <oqtopus-frontend checkout> <oqtopus-admin checkout>" >&2
    exit 2
fi

frontend_dir=$(cd "$1" && pwd)
admin_dir=$(cd "$2" && pwd)

# These values are embedded in the browser bundles at build time.
export VITE_APP_AUTH_MODE=proxy
export VITE_APP_API_ENDPOINT=/api
export VITE_APP_ACCOUNT_CONSOLE_URL="https://auth.${OQTOPUS_BASE_DOMAIN:-oqtopus.internal}:${KC_HTTPS_PORT:-9443}/realms/oqtopus/account"

(
    cd "$frontend_dir"
    export VITE_APP_APP_NAME_EN="${VITE_APP_APP_NAME_EN:-OQTOPUS}"
    export VITE_APP_APP_NAME_JA="${VITE_APP_APP_NAME_JA:-OQTOPUS}"
    bun run build
    test -s dist/index.html
)
(
    cd "$admin_dir"
    export VITE_APP_NAME="${VITE_APP_NAME:-OQTOPUS Admin}"
    npm run build
    test -s dist/index.html
)
