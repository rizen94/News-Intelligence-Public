#!/bin/bash
# Alert when the rolling NAS DB dump is older than BACKUP_MAX_AGE_HOURS (default 36).
# Exit 0 if OK or file missing with soft warning; exit 1 if stale (for monitoring hooks).

set -euo pipefail

_REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$_REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$_REPO_ROOT/.env"
  set +a
fi

_DEFAULT_DL="/mnt/nas/Data Lake Storage/news-intelligence/database-backup"
BACKUP_BASE="${BACKUP_BASE:-${NAS_BACKUP_PATH:-$_DEFAULT_DL}}"
FINAL="${BACKUP_BASE}/news_intel_latest.pgdump"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-36}"

if [ ! -f "$FINAL" ]; then
  echo "[$(date -Iseconds)] WARNING: missing rolling dump: $FINAL"
  exit 1
fi

age_sec=$(( $(date +%s) - $(stat -c %Y "$FINAL") ))
age_h=$(awk -v s="$age_sec" 'BEGIN { printf "%.1f", s/3600 }')
max_sec=$(( MAX_AGE_HOURS * 3600 ))

if [ "$age_sec" -gt "$max_sec" ]; then
  echo "[$(date -Iseconds)] ALERT: $FINAL age=${age_h}h exceeds ${MAX_AGE_HOURS}h (mtime=$(date -Iseconds -r "$FINAL"))"
  exit 1
fi

echo "[$(date -Iseconds)] OK: $FINAL age=${age_h}h (limit ${MAX_AGE_HOURS}h)"
exit 0
