#!/bin/bash
# News Intelligence — Daily database backup (run on Widow)
# Writes to /mnt/nas/backups/daily or local fallback.

set -euo pipefail

BACKUP_BASE="${BACKUP_BASE:-/mnt/nas/backups}"
if [ ! -d "$BACKUP_BASE" ]; then
  BACKUP_BASE="/opt/news-intelligence/backups"
fi
BACKUP_DIR="${BACKUP_BASE}/daily"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/news_intel_${TIMESTAMP}.pgdump"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting daily database backup..."

pg_dump -h 127.0.0.1 -U newsapp -d news_intel \
  -F custom -Z 5 \
  -f "${BACKUP_FILE}"

echo "[$(date)] Backup complete: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Remove daily backups older than 7 days
find "${BACKUP_DIR}" -name "*.pgdump" -mtime +7 -delete 2>/dev/null || true
echo "[$(date)] Old daily backups cleaned up."
