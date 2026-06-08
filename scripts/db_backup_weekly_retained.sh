#!/bin/bash
# Weekly retained Postgres backup (Phase 0 longitudinal policy).
# Writes news_intel_YYYY-MM-DD.pgdump under BACKUP_WEEKLY_DIR; prunes to BACKUP_WEEKLY_KEEP files.

set -euo pipefail

_REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$_REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.env"
  set +a
fi

BACKUP_WEEKLY_DIR="${BACKUP_WEEKLY_DIR:-/opt/news-intelligence/backups/weekly}"
BACKUP_WEEKLY_KEEP="${BACKUP_WEEKLY_KEEP:-4}"

PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
PGPORT="${PGPORT:-${DB_PORT:-5432}}"
PGUSER="${PGUSER:-${DB_USER:-newsapp}}"
PGDATABASE="${PGDATABASE:-${DB_NAME:-news_intel}}"
if [ -n "${PGPASSWORD:-}" ]; then
  export PGPASSWORD
elif [ -n "${DB_PASSWORD:-}" ]; then
  export PGPASSWORD="$DB_PASSWORD"
fi

mkdir -p "${BACKUP_WEEKLY_DIR}"
STAMP="$(date -u +%Y-%m-%d)"
OUT="${BACKUP_WEEKLY_DIR}/news_intel_${STAMP}.pgdump"
TMP="${OUT}.tmp.$$"

echo "[$(date -Iseconds)] Weekly backup → ${OUT}"
pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -F custom -Z 5 -f "$TMP"
mv -f "$TMP" "$OUT"
echo "[$(date -Iseconds)] Done $(du -h "$OUT" | awk '{print $1}')"

# Prune oldest beyond KEEP (by mtime)
mapfile -t _files < <(ls -1t "${BACKUP_WEEKLY_DIR}"/news_intel_*.pgdump 2>/dev/null || true)
if [ "${#_files[@]}" -gt "${BACKUP_WEEKLY_KEEP}" ]; then
  for f in "${_files[@]:BACKUP_WEEKLY_KEEP}"; do
    echo "[$(date -Iseconds)] Prune ${f}"
    rm -f "$f"
  done
fi
