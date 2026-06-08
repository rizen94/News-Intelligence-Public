#!/bin/bash
# Monthly retained Postgres backup (longitudinal ops — 12-month rolling window).
# Writes news_intel_YYYY-MM.pgdump under BACKUP_MONTHLY_DIR; prunes to BACKUP_MONTHLY_KEEP files.

set -euo pipefail

_REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$_REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.env"
  set +a
fi

BACKUP_MONTHLY_DIR="${BACKUP_MONTHLY_DIR:-/opt/news-intelligence/backups/monthly}"
BACKUP_MONTHLY_KEEP="${BACKUP_MONTHLY_KEEP:-12}"

PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
PGPORT="${PGPORT:-${DB_PORT:-5432}}"
PGUSER="${PGUSER:-${DB_USER:-newsapp}}"
PGDATABASE="${PGDATABASE:-${DB_NAME:-news_intel}}"
if [ -n "${PGPASSWORD:-}" ]; then
  export PGPASSWORD
elif [ -n "${DB_PASSWORD:-}" ]; then
  export PGPASSWORD="$DB_PASSWORD"
fi

mkdir -p "${BACKUP_MONTHLY_DIR}"
STAMP="$(date -u +%Y-%m)"
OUT="${BACKUP_MONTHLY_DIR}/news_intel_${STAMP}.pgdump"
TMP="${OUT}.tmp.$$"

echo "[$(date -Iseconds)] Monthly backup → ${OUT}"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -F custom -Z 5 -f "$TMP"
mv -f "$TMP" "$OUT"
echo "[$(date -Iseconds)] Done $(du -h "$OUT" | awk '{print $1}')"

mapfile -t _files < <(ls -1t "${BACKUP_MONTHLY_DIR}"/news_intel_*.pgdump 2>/dev/null || true)
if [ "${#_files[@]}" -gt "${BACKUP_MONTHLY_KEEP}" ]; then
  for _old in "${_files[@]:BACKUP_MONTHLY_KEEP}"; do
    echo "[$(date -Iseconds)] Prune ${_old}"
    rm -f "${_old}"
  done
fi
