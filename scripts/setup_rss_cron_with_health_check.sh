#!/bin/bash
# Setup cron jobs for automated RSS collection with API health check
# Runs twice a day: 6 AM and 6 PM
# Only runs RSS collection if API server is healthy

echo "Setting up automated RSS collection cron jobs with health check (twice daily)..."

# Create log directory
mkdir -p "$HOME/logs/news_intelligence"
LOG_DIR="$HOME/logs/news_intelligence"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create a wrapper script that checks API health first
WRAPPER_SCRIPT="$PROJECT_DIR/scripts/rss_collection_with_health_check.sh"

cat > "$WRAPPER_SCRIPT" << 'WRAPPER_EOF'
#!/bin/bash
# RSS Collection with API Health Check
# Only runs RSS collection if API server is running and healthy

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/logs/news_intelligence"
API_URL="http://localhost:8000/api/v4/system_monitoring/health"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting RSS collection health check..." >> "$LOG_DIR/rss_collection.log"

# Check if API server is running
if ! curl -s -f --max-time 5 "$API_URL" > /dev/null 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ API server is not running or not healthy. Skipping RSS collection." >> "$LOG_DIR/rss_collection.log"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] API health check failed. Please ensure API server is running." >> "$LOG_DIR/rss_collection.log"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ API server is healthy. Running RSS collection..." >> "$LOG_DIR/rss_collection.log"

# Run RSS collection via direct Python script (most reliable)
cd "$PROJECT_DIR/api"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5433}"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running RSS collection for all domains..." >> "$LOG_DIR/rss_collection.log"

# Use Python to run RSS collection (venv if available)
"$PYTHON_BIN" -c "
import sys
import os
sys.path.insert(0, '$PROJECT_DIR/api')

from collectors.rss_collector import collect_rss_feeds

try:
    articles = collect_rss_feeds()
    print(f'✅ Collected {articles} articles from all domains')
    sys.exit(0)
except Exception as e:
    print(f'❌ Error during RSS collection: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
" >> "$LOG_DIR/rss_collection.log" 2>&1

collection_result=$?
if [ $collection_result -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ RSS collection completed successfully" >> "$LOG_DIR/rss_collection.log"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ RSS collection failed with exit code $collection_result" >> "$LOG_DIR/rss_collection.log"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ RSS collection cycle completed" >> "$LOG_DIR/rss_collection.log"
WRAPPER_EOF

chmod +x "$WRAPPER_SCRIPT"

# Create cron job entries (twice daily: 6 AM and 6 PM)
CRON_JOBS="
# News Intelligence RSS Collection - Twice daily with API health check (6 AM and 6 PM)
0 6 * * * $WRAPPER_SCRIPT >> $LOG_DIR/rss_collection.log 2>&1
0 18 * * * $WRAPPER_SCRIPT >> $LOG_DIR/rss_collection.log 2>&1
"

# Remove any existing RSS collection cron jobs first
(crontab -l 2>/dev/null | grep -v "News Intelligence RSS Collection" | grep -v "rss_collection_with_health_check") | crontab -

# Add new cron jobs
(crontab -l 2>/dev/null; echo "$CRON_JOBS") | crontab -

echo "✅ Cron jobs installed successfully!"
echo ""
echo "📅 Collection schedule:"
echo "  - 6:00 AM (Morning) - With API health check"
echo "  - 6:00 PM (Evening) - With API health check"
echo ""
echo "🔍 Health Check:"
echo "  - Verifies API server is running at http://localhost:8000"
echo "  - Only runs RSS collection if API is healthy"
echo "  - Falls back to direct Python script if API method fails"
echo ""
echo "📄 Logs will be written to: $LOG_DIR/rss_collection.log"
echo ""
echo "To view logs:"
echo "  tail -f $LOG_DIR/rss_collection.log"
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove cron jobs:"
echo "  crontab -l | grep -v 'News Intelligence RSS Collection' | crontab -"

