#!/bin/bash
# Setup cron job to archive local logs to NAS PostgreSQL 2x/day
# Runs at 6 AM and 6 PM. Requires SSH tunnel (setup_nas_ssh_tunnel.sh).
# Uses DB_* from .env; tunnel must be active for DB connection.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$HOME/logs/news_intelligence}"
mkdir -p "$LOG_DIR"

# Python: prefer .venv
PYTHON="${PROJECT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(which python3)"
fi

# Load .env for display
if [[ -f "${PROJECT_DIR}/.env" ]]; then
    set -a
    source "${PROJECT_DIR}/.env"
    set +a
fi

echo "Setting up log archive cron (2x daily: 6 AM and 6 PM)..."
echo "  Project: $PROJECT_DIR"
echo "  Log:     $LOG_DIR/log_archive.log"
echo "  DB:      ${DB_HOST:-localhost}:${DB_PORT:-5433} (via SSH tunnel)"
echo ""

CRON_JOBS="
# News Intelligence Log Archive - Twice daily (6 AM and 6 PM)
# Moves activity.jsonl, llm_interactions.jsonl, etc. to NAS PostgreSQL
0 6 * * * cd $PROJECT_DIR && DB_HOST=\${DB_HOST:-localhost} DB_PORT=\${DB_PORT:-5433} DB_NAME=\${DB_NAME:-news_intelligence} DB_USER=\${DB_USER:-newsapp} DB_PASSWORD=\${DB_PASSWORD:-newsapp_password} $PYTHON scripts/log_archive_to_nas.py >> $LOG_DIR/log_archive.log 2>&1
0 18 * * * cd $PROJECT_DIR && DB_HOST=\${DB_HOST:-localhost} DB_PORT=\${DB_PORT:-5433} DB_NAME=\${DB_NAME:-news_intelligence} DB_USER=\${DB_USER:-newsapp} DB_PASSWORD=\${DB_PASSWORD:-newsapp_password} $PYTHON scripts/log_archive_to_nas.py >> $LOG_DIR/log_archive.log 2>&1
"

# Ensure .env is sourced in cron (cron has minimal env)
ENV_CRON="
# News Intelligence - Source .env for log archive
0 6 * * * cd $PROJECT_DIR && [ -f .env ] && export \$(grep -v '^#' .env | xargs) && $PYTHON scripts/log_archive_to_nas.py >> $LOG_DIR/log_archive.log 2>&1
0 18 * * * cd $PROJECT_DIR && [ -f .env ] && export \$(grep -v '^#' .env | xargs) && $PYTHON scripts/log_archive_to_nas.py >> $LOG_DIR/log_archive.log 2>&1
"

# Script loads .env internally; just ensure we're in project dir. Quote paths for names with spaces.
CRON_FINAL="
# News Intelligence Log Archive - 2x daily (6 AM, 6 PM)
0 6 * * * cd \"$PROJECT_DIR\" && \"$PYTHON\" scripts/log_archive_to_nas.py >> \"$LOG_DIR/log_archive.log\" 2>&1
0 18 * * * cd \"$PROJECT_DIR\" && \"$PYTHON\" scripts/log_archive_to_nas.py >> \"$LOG_DIR/log_archive.log\" 2>&1
"

# Replace existing log archive cron with new entries
CURRENT=$(crontab -l 2>/dev/null || true)
FILTERED=$(echo "$CURRENT" | grep -v "News Intelligence Log Archive" | grep -v "log_archive_to_nas.py" || true)
(echo "$FILTERED"; echo "$CRON_FINAL") | crontab -

echo "✅ Cron installed."
echo ""
echo "Schedule: 6:00 AM and 6:00 PM"
echo "Prerequisite: SSH tunnel must be running (start_system.sh or setup_nas_ssh_tunnel.sh)"
echo ""
echo "Test run:  cd $PROJECT_DIR && $PYTHON scripts/log_archive_to_nas.py --dry-run"
echo "View log:  tail -f $LOG_DIR/log_archive.log"
echo "Crontab:   crontab -l"
