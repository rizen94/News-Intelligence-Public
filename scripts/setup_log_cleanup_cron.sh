#!/bin/bash
# Setup cron to delete old pipeline_trace.log files (older than 7 days).
# Run once; path is quoted so "News Intelligence" is not split by cron.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="${PROJECT_DIR}/logs"

CRON_LINE="0 2 * * * find \"${LOGS_DIR}\" -name 'pipeline_trace.log*' -mtime +7 -delete"

# Remove any existing News Intelligence log cleanup line
CURRENT=$(crontab -l 2>/dev/null || true)
FILTERED=$(echo "$CURRENT" | grep -v "pipeline_trace.log" | grep -v "News Intelligence.*logs.*delete" || true)

# Add our line (with comment)
(echo "$FILTERED"; echo ""; echo "# News Intelligence - delete old pipeline_trace.log (7+ days)"; echo "$CRON_LINE") | crontab -

echo "✅ Log cleanup cron installed (daily at 2 AM)."
echo "   Deletes: $LOGS_DIR/pipeline_trace.log* older than 7 days"
echo "   Crontab: crontab -l"
