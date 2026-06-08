#!/bin/bash
# Post-boot verification for News Intelligence on Widow.
# Exit 0 when core services and API readiness checks pass.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

API_BASE="${API_BASE_URL:-http://127.0.0.1:8000}"
READINESS_URL="${API_BASE}/api/system_monitoring/startup/readiness"
AUTOMATION_URL="${API_BASE}/api/system_monitoring/automation/status"
FAIL=0

check_systemd() {
  local unit="$1"
  if systemctl is-active --quiet "$unit" 2>/dev/null; then
    echo "✅ $unit active"
  else
    echo "❌ $unit not active"
    FAIL=1
  fi
}

echo "=== News Intelligence boot verification ==="
echo ""

for unit in postgresql pgbouncer ollama nginx news-intelligence-api-public newsplatform-secondary; do
  if systemctl list-unit-files "${unit}.service" &>/dev/null 2>&1; then
    check_systemd "$unit" || true
  else
    echo "⚠️  $unit not installed — skipped"
  fi
done

echo ""
echo "Waiting for API readiness..."
ready=0
for i in $(seq 1 12); do
  if response=$(curl -sf --max-time 5 "$READINESS_URL" 2>/dev/null); then
    if echo "$response" | grep -q '"ready"[[:space:]]*:[[:space:]]*true'; then
      echo "✅ Readiness OK (attempt $i)"
      ready=1
      break
    fi
  fi
  sleep 5
done
if [ "$ready" -ne 1 ]; then
  echo "❌ Readiness endpoint did not report ready"
  FAIL=1
fi

echo ""
if curl -sf --max-time 10 "$AUTOMATION_URL" >/dev/null 2>&1; then
  workers=$(curl -sf --max-time 10 "$AUTOMATION_URL" | python3 -c "import sys,json; d=json.load(sys.stdin).get('data',{}); print(d.get('active_workers',0), d.get('max_concurrent_tasks','?'))" 2>/dev/null || echo "? ?")
  echo "✅ Automation status: workers $workers"
else
  echo "❌ Automation status unreachable"
  FAIL=1
fi

echo ""
if command -v ollama >/dev/null 2>&1; then
  for model in llama3.1:8b nomic-embed-text qwen2.5:7b; do
    if ollama list 2>/dev/null | grep -q "$model"; then
      echo "✅ Ollama model: $model"
    else
      echo "⚠️  Ollama model missing: $model"
    fi
  done
fi

echo ""
LOG_FILE="${PROJECT_DIR}/logs/widow_db_adjacent.log"
if [ -f "$LOG_FILE" ]; then
  echo "Recent db-adjacent cron (last 3 lines):"
  tail -3 "$LOG_FILE" || true
else
  echo "⚠️  No widow_db_adjacent.log yet"
fi

POPOS_HOST="${OLLAMA_POP_OS_HOST:-http://192.168.93.99:11434}"
if curl -sf --max-time 3 "${POPOS_HOST}/api/tags" >/dev/null 2>&1; then
  echo "✅ PopOS Ollama reachable at $POPOS_HOST"
else
  echo "⚠️  PopOS Ollama unreachable (70B finisher degraded)"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "=== Boot verification PASSED ==="
  exit 0
fi
echo "=== Boot verification FAILED ==="
exit 1
