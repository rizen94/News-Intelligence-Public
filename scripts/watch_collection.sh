#!/bin/bash
# Watch data collection / pipeline progress.
# Polls pipeline status and optionally tails the API log so you can see stages as they run.
# Usage:
#   ./scripts/watch_collection.sh           # status every 5s, no log tail
#   ./scripts/watch_collection.sh --logs     # status + tail API log
#   ./scripts/watch_collection.sh --interval 10

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

API="${API_URL:-http://localhost:8000}"
STATUS_URL="$API/api/system_monitoring/pipeline_status"
INTERVAL=5
TAIL_LOGS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --logs)      TAIL_LOGS=true; shift ;;
        --interval)  INTERVAL="$2"; shift 2 ;;
        *)           shift ;;
    esac
done

LOG_FILE="${LOG_FILE:-logs/api_server.log}"

echo "=========================================="
echo "Data collection / pipeline watch"
echo "=========================================="
echo "  Status URL: $STATUS_URL"
echo "  Poll every: ${INTERVAL}s"
echo "  Log file:   $LOG_FILE"
if $TAIL_LOGS && [[ -f "$LOG_FILE" ]]; then
    echo "  Tailing:    yes (last 5 lines + new)"
else
    echo "  Tailing:    no (use --logs to enable)"
fi
echo "  Press Ctrl+C to stop"
echo "=========================================="
echo ""

last_status=""
while true; do
    TS=$(date '+%H:%M:%S')
    JSON=$(curl -s "$STATUS_URL" 2>/dev/null || echo '{"success":false}')
    if echo "$JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    if not d.get('success'):
        print('  [' + '$TS' + '] Could not get pipeline status (API down or error)')
        sys.exit(0)
    data = d.get('data', {})
    status = data.get('pipeline_status', 'unknown')
    progress = data.get('overall_progress', 0)
    recent = data.get('recent_traces', [])[:3]
    total = data.get('articles_processed', 0)
    analyzed = data.get('articles_analyzed', 0)
    recent_1h = data.get('recent_articles', 0)
    print('  [' + '$TS' + '] Pipeline: ' + status + ' | Progress: ' + str(progress) + '% | Articles: ' + str(total) + ' total, ' + str(analyzed) + ' analyzed, ' + str(recent_1h) + ' last 1h')
    for t in recent:
        tid = t.get('trace_id', '')[:22]
        st = t.get('status', '')
        print('    trace ' + tid + ' ... ' + st)
except Exception as e:
    print('  [' + '$TS' + '] Parse error: ' + str(e))
" 2>/dev/null; then
        :
    else
        echo "  [$TS] Failed to parse pipeline status"
    fi

    if $TAIL_LOGS && [[ -f "$LOG_FILE" ]]; then
        echo "  --- recent log (pipeline / RSS) ---"
        grep -E "pipeline_|RSS|rss_collection|topic_clustering|ai_analysis|articles added" "$LOG_FILE" 2>/dev/null | tail -5
        echo ""
    fi

    sleep "$INTERVAL"
done
