#!/bin/bash
# Monitor LLM Processing Progress
# Shows real-time LLM activity, queue status, and processing statistics

echo "=========================================="
echo "LLM Processing Progress Monitor"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Quick Status
echo "📊 Quick Status:"
echo "----------------"
STATUS=$(curl -s "http://localhost:8000/api/v4/content_analysis/llm/status")
if [ $? -eq 0 ]; then
    echo "$STATUS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        print(f\"  LLM Available: {'✅' if data.get('llm_available') else '❌'}\")
        print(f\"  Active Tasks: {data.get('active_tasks', 0)}\")
        print(f\"  Last Activity: {data.get('last_activity', 'Never')}\")
        if data.get('current_tasks'):
            print(f\"  Current Tasks:\")
            for task in data['current_tasks']:
                print(f\"    - {task.get('type')} (Article {task.get('article_id')}, {task.get('duration_seconds', 0):.1f}s)\")
    else:
        print('  ❌ Error getting status')
except:
    print('  ❌ Failed to parse response')
"
else
    echo "  ❌ Failed to connect to API"
fi

echo ""
echo "📋 Queue Status (All Domains):"
echo "-------------------------------"
for domain in politics finance science-tech; do
    QUEUE=$(curl -s "http://localhost:8000/api/v4/$domain/content_analysis/topics/queue/status")
    if [ $? -eq 0 ]; then
        echo "$QUEUE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        stats = data.get('stats', {})
        worker = '✅' if data.get('worker_running') else '❌'
        print(f\"  $domain: Worker {worker} | Pending: {stats.get('pending', 0)} | Processing: {stats.get('processing', 0)} | Completed: {stats.get('completed', 0)} | Failed: {stats.get('failed', 0)}\")
    else:
        print(f\"  $domain: ❌ Error\")
except:
    print(f\"  $domain: ❌ Failed to parse\")
"
    fi
done

echo ""
echo "📈 Dashboard Summary:"
echo "---------------------"
DASHBOARD=$(curl -s "http://localhost:8000/api/v4/content_analysis/llm/dashboard")
if [ $? -eq 0 ]; then
    echo "$DASHBOARD" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        llm = data.get('llm_status', {})
        stats = data.get('statistics', {})
        queue = data.get('queue_status', {})
        
        print(f\"  LLM Available: {'✅' if llm.get('available') else '❌'}\")
        print(f\"  Active Tasks: {llm.get('is_active', False) and 'Yes' or 'No'}\")
        print(f\"  Total Tasks: {stats.get('total_tasks', 0)}\")
        print(f\"  Completed: {stats.get('completed_tasks', 0)}\")
        print(f\"  Failed: {stats.get('failed_tasks', 0)}\")
        print(f\"  Success Rate: {stats.get('success_rate', 0)*100:.1f}%\")
        print(f\"  Last Activity: {llm.get('last_activity', 'Never')}\")
        print(f\"\")
        print(f\"  Queue Status:\")
        for schema, qstats in queue.items():
            pending = qstats.get('pending', 0)
            processing = qstats.get('processing', 0)
            completed = qstats.get('completed', 0)
            failed = qstats.get('failed', 0)
            total = pending + processing + completed + failed
            if total > 0:
                pct = (completed / total * 100) if total > 0 else 0
                print(f\"    {schema}: {pending} pending, {processing} processing, {completed} completed ({pct:.1f}%), {failed} failed\")
    else:
        print('  ❌ Error getting dashboard')
except Exception as e:
    print(f'  ❌ Failed to parse: {e}')
"
else
    echo "  ❌ Failed to connect to API"
fi

echo ""
echo "=========================================="
echo "💡 Tip: Run this script in a loop to monitor continuously:"
echo "   watch -n 5 ./scripts/monitor_llm_progress.sh"
echo "=========================================="

