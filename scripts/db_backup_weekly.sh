#!/bin/bash
# News Intelligence — Weekly database backup (run on Widow)
# Writes to /mnt/nas/backups/weekly or local fallback.

set -euo pipefail

BACKUP_BASE="${BACKUP_BASE:-/mnt/nas/backups}"
if [ ! -d "$BACKUP_BASE" ]; then
  BACKUP_BASE="/opt/news-intelligence/backups"
fi
BACKUP_DIR="${BACKUP_BASE}/weekly"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/news_intel_weekly_${TIMESTAMP}.pgdump"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting weekly database backup..."

pg_dump -h 127.0.0.1 -U newsapp -d news_intel \
  -F custom -Z 9 \
  -f "${BACKUP_FILE}"

echo "[$(date)] Weekly backup complete: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Remove weekly backups older than 30 days
find "${BACKUP_DIR}" -name "*.pgdump" -mtime +30 -delete 2>/dev/null || true
echo "[$(date)] Old weekly backups cleaned up."
