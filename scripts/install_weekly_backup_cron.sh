#!/bin/bash
# Install Sunday weekly retained Postgres backup cron on Widow (Phase 0/6).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CRON_LINE="30 4 * * 0 cd ${REPO} && ${REPO}/scripts/db_backup_weekly_retained.sh >> ${REPO}/logs/weekly_backup.log 2>&1"
mkdir -p "${REPO}/logs"
( crontab -l 2>/dev/null | grep -v 'db_backup_weekly_retained.sh' || true; echo "$CRON_LINE" ) | crontab -
echo "Installed weekly backup cron:"
echo "  $CRON_LINE"
