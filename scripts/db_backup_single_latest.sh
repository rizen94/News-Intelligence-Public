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

# Prevent concurrent dumps (USB/NAS thrash + partial .tmp races)
mkdir -p /opt/news-intelligence/logs
exec 9>/opt/news-intelligence/logs/db_backup_single.lock
if ! flock -n 9; then
  echo "[$(date -Iseconds)] SKIP: another db_backup_single_latest.sh holds the lock"
  exit 0
fi

# Survive caller hangup (SSH / systemd-run waiters)
trap '' HUP

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
PRESSURE_JSON="${DISK_IO_PRESSURE_JSON:-/run/news-intelligence/disk_io_pressure.json}"
MAX_DEFER="${BACKUP_MAX_DEFER:-6}"
# Must be writable by cron user (pete) — do not use /run/news-intelligence (root-owned)
DEFER_COUNT_FILE="${BACKUP_DEFER_COUNT_FILE:-/opt/news-intelligence/logs/db_backup_defer_count}"

# USB root: skip+reschedule when governor says defer_heavy_writes (same class as apt).
_should_defer_heavy() {
  if [ "${NEWS_INTEL_BACKUP_FORCE:-}" = "1" ]; then
    return 1
  fi
  if [ ! -f "$PRESSURE_JSON" ]; then
    return 1
  fi
  python3 - "$PRESSURE_JSON" <<'PY'
import json, sys, time
path = sys.argv[1]
try:
    d = json.load(open(path))
except Exception:
    sys.exit(1)  # treat unreadable as defer-open (do not block)
updated = d.get("updated_at") or d.get("written_at") or ""
# Stale samples fail-open (do not defer forever if governor died)
try:
    from datetime import datetime, timezone
    ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
    if time.time() - ts > 120:
        sys.exit(1)
except Exception:
    pass
sys.exit(0 if d.get("defer_heavy_writes") else 1)
PY
}

_bump_defer_count() {
  local today count
  today="$(date +%F)"
  mkdir -p "$(dirname "$DEFER_COUNT_FILE")"
  if [ -f "$DEFER_COUNT_FILE" ] && [ "$(awk '{print $1}' "$DEFER_COUNT_FILE")" = "$today" ]; then
    count="$(awk '{print $2}' "$DEFER_COUNT_FILE")"
  else
    count=0
  fi
  count=$((count + 1))
  echo "$today $count" >"$DEFER_COUNT_FILE"
  echo "$count"
}

_reschedule() {
  local count
  count="$(_bump_defer_count)"
  if [ "$count" -gt "$MAX_DEFER" ]; then
    echo "[$(date -Iseconds)] ABORT: disk still hot after $MAX_DEFER backup defers today"
    exit 1
  fi
  echo "[$(date -Iseconds)] DEFER: USB disk IO heavy (defer #$count/$MAX_DEFER); sleep 30min then retry"
  # pete cron cannot create systemd transient timers without polkit; use background sleep.
  nohup bash -c \
    "sleep 1800; exec /opt/news-intelligence/scripts/db_backup_single_latest.sh" \
    >>/opt/news-intelligence/logs/backup.log 2>&1 &
  disown || true
  exit 0
}

if _should_defer_heavy; then
  _reschedule
fi

mkdir -p "${BACKUP_BASE}"
mkdir -p /opt/news-intelligence/logs

echo "[$(date -Iseconds)] Starting single-file backup → ${FINAL} (host=${PGHOST} db=${PGDATABASE})"

nice -n 19 ionice -c3 pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" \
  -F custom -Z 5 \
  -f "$TMP"

mv -f -- "$TMP" "$FINAL"

echo "[$(date -Iseconds)] Backup complete: ${FINAL} ($(du -h "${FINAL}" | cut -f1))"
