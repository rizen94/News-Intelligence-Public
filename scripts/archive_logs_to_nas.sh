#!/usr/bin/env bash
# Archive log files from Widow (or project) to NAS and trim local copies so Widow stays clean.
# Run on Widow: ensure NAS is mounted at NAS_MOUNT (e.g. /mnt/nas).
# Cron example: 0 5 * * * /opt/news-intelligence/scripts/archive_logs_to_nas.sh >> /opt/news-intelligence/logs/archive_logs.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${LOG_DIR:-$PROJECT_ROOT/logs}"

# Where to archive on NAS (must be writable; create if missing)
NAS_MOUNT="${NAS_MOUNT:-/mnt/nas}"
NAS_LOG_ARCHIVE="${NAS_LOG_ARCHIVE:-$NAS_MOUNT/news-intelligence/logs}"
# Keep this many days of local logs before archiving (only files older than this are moved)
ARCHIVE_OLDER_THAN_DAYS="${ARCHIVE_OLDER_THAN_DAYS:-7}"

if [ ! -d "$LOG_DIR" ]; then
  echo "[$(date)] No log dir: $LOG_DIR"
  exit 0
fi

if [ ! -d "$NAS_MOUNT" ] || ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
  echo "[$(date)] NAS not mounted at $NAS_MOUNT — skipping log archive"
  exit 0
fi

mkdir -p "$NAS_LOG_ARCHIVE"
YMD=$(date +%Y-%m-%d)
ARCHIVE_SUBDIR="$NAS_LOG_ARCHIVE/$YMD"
mkdir -p "$ARCHIVE_SUBDIR"

count=0
while IFS= read -r -d '' f; do
  b="$(basename "$f")"
  dest="$ARCHIVE_SUBDIR/$b"
  if [ -f "$dest" ]; then
    dest="$ARCHIVE_SUBDIR/${b%.*}_$(date +%H%M%S).${b##*.}"
  fi
  cp -a "$f" "$dest" && { : > "$f"; count=$((count + 1)); }
done < <(find "$LOG_DIR" -maxdepth 1 -type f \( -name '*.jsonl' -o -name '*.log' \) -mtime +"$ARCHIVE_OLDER_THAN_DAYS" -print0 2>/dev/null)

echo "[$(date)] Archived $count log file(s) to $ARCHIVE_SUBDIR"

# Optional: remove NAS archive dirs older than 90 days to cap NAS usage
find "$NAS_LOG_ARCHIVE" -maxdepth 1 -type d -mtime +90 -exec rm -rf {} \; 2>/dev/null || true
