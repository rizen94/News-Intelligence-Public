#!/usr/bin/env bash
# Build the News Intelligence web SPA and deploy dist to both Widow locations.
#
# Production nginx serves /var/www/news-intelligence/web/dist (public HTTPS).
# The dev/runtime tree also keeps /opt/news-intelligence/web/dist — sync both.
#
# Usage (on Widow):
#   ./web/scripts/deploy-web-dist.sh
#
# Optional env:
#   SKIP_BUILD=1   — rsync existing web/dist only
#   DEPLOY_HOST=   — default localhost (run on Widow)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="${ROOT}/dist"
OPT_TARGET="/opt/news-intelligence/web/dist"
WWW_TARGET="/var/www/news-intelligence/web/dist"

echo "==> News Intelligence web deploy"
echo "    source: ${DIST}"

if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "==> Building (vite production)…"
  (cd "${ROOT}" && npm ci --silent 2>/dev/null || true)
  (cd "${ROOT}" && npx vite build)
fi

if [[ ! -d "${DIST}" ]]; then
  echo "ERROR: ${DIST} not found. Run vite build first." >&2
  exit 1
fi

for TARGET in "${OPT_TARGET}" "${WWW_TARGET}"; do
  echo "==> Rsync → ${TARGET}"
  mkdir -p "${TARGET}"
  rsync -a --delete "${DIST}/" "${TARGET}/"
done

echo "==> Deploy complete ($(date -Is))"
echo "    ${OPT_TARGET}"
echo "    ${WWW_TARGET}"
