#!/bin/bash
# News Intelligence — Single rolling DB backup for NAS cold storage (homelab)
#
# Policy: ONE file on cold storage, replaced each run (no dated retention → minimal wasted space).
# RPO ≈ time since last successful run (~24h with daily cron). Restore = consistent snapshot at
# dump start; commits after that moment are not in the file.
#
# Default destination: Data Lake share (CIFS //192.168.93.100/public/.../Data Lake Storage/...)
#
# Env:
#   BACKUP_BASE — output directory (default below)
#   DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME — from project .env (optional auto-load)
#   PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE — standard libpq overrides
#
# Optional: NEWS_INTEL_BACKUP_FALLBACK_LOCAL=1 — if Data Lake path is missing, use
#   /opt/news-intelligence/backups/single (Widow local).
#
# Cron example (03:15 daily):
#   15 3 * * * user /opt/news-intelligence/scripts/db_backup_single_latest.sh >> /opt/news-intelligence/logs/backup.log 2>&1

set -euo pipefail

_REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$_REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.env"
  set +a
fi

# Default NAS path: smb://192.168.93.100/public/Data Lake Storage/... → /mnt/nas/Data Lake Storage/...
# configs/env.example: NAS_BACKUP_PATH
_DEFAULT_DL="/mnt/nas/Data Lake Storage/news-intelligence/database-backup"
BACKUP_BASE="${BACKUP_BASE:-${NAS_BACKUP_PATH:-$_DEFAULT_DL}}"
if [ "${NEWS_INTEL_BACKUP_FALLBACK_LOCAL:-}" = "1" ] && [ ! -d "/mnt/nas/Data Lake Storage" ]; then
  BACKUP_BASE="/opt/news-intelligence/backups/single"
fi

PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
PGPORT="${PGPORT:-${DB_PORT:-5432}}"
PGUSER="${PGUSER:-${DB_USER:-newsapp}}"
PGDATABASE="${PGDATABASE:-${DB_NAME:-news_intel}}"
if [ -n "${PGPASSWORD:-}" ]; then
  export PGPASSWORD
elif [ -n "${DB_PASSWORD:-}" ]; then
  export PGPASSWORD="$DB_PASSWORD"
else
  unset PGPASSWORD 2>/dev/null || true
fi

FINAL="${BACKUP_BASE}/news_intel_latest.pgdump"
TMP="${FINAL}.tmp.$$"

mkdir -p "${BACKUP_BASE}"

echo "[$(date -Iseconds)] Starting single-file backup → ${FINAL} (host=${PGHOST} db=${PGDATABASE})"

pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  -F custom -Z 5 \
  -f "$TMP"

mv -f -- "$TMP" "$FINAL"

echo "[$(date -Iseconds)] Backup complete: ${FINAL} ($(du -h "${FINAL}" | cut -f1))"
