#!/usr/bin/env bash
# Build the SPA (Vite bundle) and rsync web/dist to Widow nginx document root.
# Run from project root on your dev machine (same network as Widow).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WIDOW_HOST="${WIDOW_HOST:-192.168.93.101}"
WIDOW_USER="${WIDOW_USER:-pete}"
REMOTE_DIST="${REMOTE_DIST:-/var/www/news-intelligence/web/dist}"

cd "${ROOT}/web"
if [[ "${SKIP_BUILD:-}" != "1" ]]; then
  npm run build:bundle
fi

echo "Rsync dist/ → ${WIDOW_USER}@${WIDOW_HOST}:${REMOTE_DIST}/"
rsync -avz --delete "${ROOT}/web/dist/" "${WIDOW_USER}@${WIDOW_HOST}:${REMOTE_DIST}/"
echo "Done. Open https://<your-public-hostname>/ on the LAN with curl -k for self-signed tests."
