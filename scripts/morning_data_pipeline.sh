#!/bin/bash
# Morning Data Pipeline: RSS collection + entity extraction + topic extraction

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$PROJECT_DIR/api"
LOG_DIR="${LOG_DIR:-$HOME/logs/news_intelligence}"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/morning_pipeline_$(date '+%Y%m%d').log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========== Morning Data Pipeline Starting ==========" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Project: $PROJECT_DIR" >> "$LOG_FILE"

cd "$API_DIR"

# DB: for Widow use DB_HOST=192.168.93.101 DB_PORT=5432 (or set in .env)
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5433}"
export DB_NAME="${DB_NAME:-news_intelligence}"
export DB_USER="${DB_USER:-newsapp}"
export DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"

# Run RSS + entity + topic processing (using venv if available)
"$PYTHON_BIN" scripts/run_rss_and_process_all.py >> "$LOG_FILE" 2>&1
RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========== Pipeline completed successfully ==========" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ========== Pipeline exited with code $RESULT ==========" >> "$LOG_FILE"
fi

exit $RESULT
