#!/bin/bash
# Setup daily batch processing cron job for 4am
# Processes RSS feeds, ML analysis, and topic clustering

set -e

echo "=========================================="
echo "Daily Batch Processor Setup"
echo "=========================================="

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# Create log directory
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
echo "Log directory: $LOG_DIR"

# Make script executable
chmod +x "$PROJECT_DIR/api/scripts/daily_batch_processor.py"

# Create Python wrapper script
WRAPPER_SCRIPT="$PROJECT_DIR/scripts/run_daily_batch.sh"
cat > "$WRAPPER_SCRIPT" << 'EOF'
#!/bin/bash
# Wrapper script for daily batch processor
# Ensures proper environment and error handling

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/api:$PWD:$PYTHONPATH"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the batch processor
python3 api/scripts/daily_batch_processor.py

# Exit with the script's exit code
exit $?
EOF

chmod +x "$WRAPPER_SCRIPT"
echo "Created wrapper script: $WRAPPER_SCRIPT"

# Remove existing daily batch cron job if it exists
crontab -l 2>/dev/null | grep -v "daily_batch_processor\|run_daily_batch" | crontab - 2>/dev/null || true

# Add new cron job for 4am daily
CRON_JOB="0 4 * * * $WRAPPER_SCRIPT >> $LOG_DIR/daily_batch_cron.log 2>&1"

# Add to crontab
(crontab -l 2>/dev/null; echo "# News Intelligence Daily Batch Processor - Runs at 4am"; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Daily batch processor installed successfully!"
echo ""
echo "Schedule:"
echo "  - Runs daily at 4:00 AM"
echo ""
echo "Processing Pipeline:"
echo "  1. RSS Feed Processing (collect new articles)"
echo "  2. ML Processing (sentiment, quality, entities)"
echo "  3. Topic Clustering (auto-tagging)"
echo "  4. Statistics Update"
echo ""
echo "Logs:"
echo "  - Daily logs: $LOG_DIR/daily_batch_YYYYMMDD.log"
echo "  - Cron logs: $LOG_DIR/daily_batch_cron.log"
echo ""
echo "To view today's log:"
echo "  tail -f $LOG_DIR/daily_batch_$(date +%Y%m%d).log"
echo ""
echo "To test the batch processor manually:"
echo "  $WRAPPER_SCRIPT"
echo ""
echo "To view cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v 'run_daily_batch' | crontab -"
echo ""

