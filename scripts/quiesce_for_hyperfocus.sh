#!/usr/bin/env bash
# Full Widow quiesce for hyperfocus backlog burndown (API stopped, competitors killed).
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
STATE="$ROOT/data/hyperfocus_state.json"
BASELINE="$ROOT/logs/hyperfocus_baseline_$(date -u +%Y%m%dT%H%M%SZ).txt"
CRON_SRC="/etc/cron.d/widow-db-adjacent"
CRON_DISABLED="/etc/cron.d/widow-db-adjacent.disabled"

cd "$ROOT"
mkdir -p "$ROOT/logs" "$ROOT/data"

echo "=== Hyperfocus quiesce $(date -u -Iseconds) ===" | tee "$BASELINE"
{
  echo "--- pending snapshot ---"
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  if [[ -f "$ROOT/.db_password_widow" ]]; then
    export DB_PASSWORD
    DB_PASSWORD="$(cat "$ROOT/.db_password_widow")"
  fi
  set +a
  export PYTHONPATH=api
  .venv/bin/python3 - <<'PY' || true
from services.backlog_metrics import invalidate_backlog_metrics_cache, get_all_pending_counts
invalidate_backlog_metrics_cache()
p = get_all_pending_counts()
for k in sorted(p.keys()):
    if int(p.get(k) or 0) > 0:
        print(f"  {k}: {p[k]}")
PY
  echo "--- processes before kill ---"
  pgrep -af "run_major_backlog|bulk_catchup|catchup_topic|run_widow_db_adjacent|run_secondary_worker" || true
} >>"$BASELINE" 2>&1

# Kill ad-hoc catch-ups and competitors
for pattern in \
  "run_major_backlog_catchup.py" \
  "bulk_catchup.py" \
  "catchup_topic_clustering.py" \
  "run_widow_db_adjacent.py" \
  "run_secondary_worker.py"; do
  pkill -f "$pattern" 2>/dev/null || true
done
sleep 2

# Pause marker + secondary/NRI (does not stop API)
"$ROOT/scripts/pause_for_bulk_catchup.sh"

API_WAS_ACTIVE=false
systemctl is-active --quiet news-intelligence-api-public 2>/dev/null && API_WAS_ACTIVE=true

if [[ "$API_WAS_ACTIVE" == true ]]; then
  echo "Stopping news-intelligence-api-public"
  sudo systemctl stop news-intelligence-api-public
fi

sudo systemctl stop newsplatform-secondary 2>/dev/null || true

CRON_WAS_ENABLED=false
if [[ -f "$CRON_SRC" ]]; then
  CRON_WAS_ENABLED=true
  echo "Disabling widow-db-adjacent cron"
  sudo mv "$CRON_SRC" "$CRON_DISABLED"
fi

python3 - <<PY
import json
from datetime import datetime, timezone
from pathlib import Path

state_path = Path("$STATE")
state = {}
if state_path.is_file():
    try:
        state = json.loads(state_path.read_text())
    except Exception:
        state = {}
state.update({
    "quiesced_at": datetime.now(timezone.utc).isoformat(),
    "api_was_active": $([ "$API_WAS_ACTIVE" = true ] && echo True || echo False),
    "cron_was_enabled": $([ "$CRON_WAS_ENABLED" = true ] && echo True || echo False),
    "baseline_log": "$BASELINE",
})
state_path.write_text(json.dumps(state, indent=2))
print(f"Wrote {state_path}")
PY

echo "Quiesce complete. API: $(systemctl is-active news-intelligence-api-public 2>/dev/null || echo inactive)"
echo "Baseline: $BASELINE"
