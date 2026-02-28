#!/bin/bash
# Setup cron jobs for morning data pipeline
# Runs: RSS collection + entity extraction + topic extraction
# Schedule: Multiple batches overnight/early morning for fresh data by breakfast

set -e

echo "Setting up morning data pipeline cron jobs..."

# Create log directory
mkdir -p "$HOME/logs/news_intelligence"
LOG_DIR="$HOME/logs/news_intelligence"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$PROJECT_DIR/api"

# Create wrapper script that runs full pipeline
WRAPPER_SCRIPT="$PROJECT_DIR/scripts/morning_data_pipeline.sh"

cat > "$WRAPPER_SCRIPT" << WRAPPER_EOF
#!/bin/bash
# Morning Data Pipeline: RSS collection + entity extraction + topic extraction

PROJECT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="\$PROJECT_DIR/api"
LOG_DIR="\${LOG_DIR:-\$HOME/logs/news_intelligence}"
PYTHON_BIN="\$PROJECT_DIR/.venv/bin/python"
[ -x "\$PYTHON_BIN" ] || PYTHON_BIN="python3"

mkdir -p "\$LOG_DIR"
LOG_FILE="\$LOG_DIR/morning_pipeline_\$(date '+%Y%m%d').log"

echo "[\$(date '+%Y-%m-%d %H:%M:%S')] ========== Morning Data Pipeline Starting ==========" >> "\$LOG_FILE"
echo "[\$(date '+%Y-%m-%d %H:%M:%S')] Project: \$PROJECT_DIR" >> "\$LOG_FILE"

cd "\$API_DIR"
export DB_HOST="\${DB_HOST:-localhost}"
export DB_PORT="\${DB_PORT:-5433}"

# Run RSS + entity + topic processing (using venv if available)
"\$PYTHON_BIN" scripts/run_rss_and_process_all.py >> "\$LOG_FILE" 2>&1
RESULT=\$?

if [ \$RESULT -eq 0 ]; then
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] ========== Pipeline completed successfully ==========" >> "\$LOG_FILE"
else
    echo "[\$(date '+%Y-%m-%d %H:%M:%S')] ========== Pipeline exited with code \$RESULT ==========" >> "\$LOG_FILE"
fi

exit \$RESULT
WRAPPER_EOF

chmod +x "$WRAPPER_SCRIPT"

# Cron: Run at 4 AM, 5 AM, 6 AM (three batches for fresh morning data)
CRON_JOBS="
# News Intelligence Morning Data Pipeline - RSS + entity + topic extraction
# Run 3 batches between 4-6 AM for fresh data by morning
0 4 * * * $WRAPPER_SCRIPT
0 5 * * * $WRAPPER_SCRIPT
0 6 * * * $WRAPPER_SCRIPT
"

# Remove any existing pipeline cron jobs
(crontab -l 2>/dev/null | grep -v "News Intelligence Morning Data Pipeline" | grep -v "morning_data_pipeline") | crontab - || true

# Add new cron jobs
(crontab -l 2>/dev/null; echo "$CRON_JOBS") | crontab -

echo "✅ Morning data pipeline cron jobs installed!"
echo ""
echo "📅 Schedule (3 batches for fresh data):"
echo "  - 4:00 AM - RSS collection + entity/topic extraction"
echo "  - 5:00 AM - RSS collection + entity/topic extraction"
echo "  - 6:00 AM - RSS collection + entity/topic extraction"
echo ""
echo "📋 Each run:"
echo "  1. Pulls latest from all RSS feeds"
echo "  2. Queues unprocessed articles"
echo "  3. Runs entity extraction (people, orgs, dates, countries)"
echo "  4. Runs topic extraction via LLM"
echo ""
echo "📄 Logs: $LOG_DIR/morning_pipeline_YYYYMMDD.log"
echo ""
echo "To view today's log:"
echo "  tail -f $LOG_DIR/morning_pipeline_\$(date '+%Y%m%d').log"
echo ""
echo "To run manually:"
echo "  $WRAPPER_SCRIPT"
echo ""
echo "To remove cron jobs:"
echo "  crontab -l | grep -v 'Morning Data Pipeline' | grep -v 'morning_data_pipeline' | crontab -"
