#!/bin/bash
# RSS Collection with API Health Check
# Only runs RSS collection if API server is running and healthy

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/logs/news_intelligence"
API_URL="http://localhost:8000/api/system_monitoring/health"
[ -f "\${PROJECT_DIR}/.env" ] && set -a && source "\${PROJECT_DIR}/.env" && set +a

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
export DB_HOST="${DB_HOST:-192.168.93.101}"
export DB_PORT="${DB_PORT:-5432}"

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
