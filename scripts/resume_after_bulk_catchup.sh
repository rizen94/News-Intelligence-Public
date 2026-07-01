#!/usr/bin/env bash
# Resume NI/NRI services after bulk catch-up.
set -euo pipefail

ROOT="${NEWS_INTEL_ROOT:-/opt/news-intelligence}"
MARKER="$ROOT/data/bulk_catchup_competition_pause.json"
STATE="$ROOT/data/bulk_catchup_pause_services.json"

cd "$ROOT"

INHIBIT_PID_FILE="$ROOT/data/bulk_catchup_sleep_inhibit.pid"
if [[ -f "$INHIBIT_PID_FILE" ]]; then
  pid="$(cat "$INHIBIT_PID_FILE" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "Stopped sleep inhibit (pid $pid)"
  fi
  rm -f "$INHIBIT_PID_FILE"
fi

PYTHONPATH=api .venv/bin/python3 - <<'PY'
from shared.bulk_catchup_pause import clear_pause_marker
clear_pause_marker()
print("Cleared competition pause marker")
PY

if [[ -f "$ROOT/.env" ]]; then
  sed -i 's/^PIPELINE_BACKFILL_MODE=true/PIPELINE_BACKFILL_MODE=false/' "$ROOT/.env" 2>/dev/null || true
  sed -i '/^PIPELINE_BACKFILL_COLLECTION_RESUME_AT=/d' "$ROOT/.env" 2>/dev/null || true
fi

restore_bool() {
  local key="$1" val="$2"
  [[ "$val" == "true" ]]
}

if [[ -f "$STATE" ]]; then
  eval "$(python3 - <<PY
import json
from pathlib import Path
d = json.loads(Path("$STATE").read_text())
for k, v in d.items():
    print(f'{k}={str(v).lower()}')
PY
)"
  if restore_bool newsplatform_secondary_was_active "${newsplatform_secondary_was_active:-false}"; then
    echo "Starting newsplatform-secondary"
    sudo systemctl start newsplatform-secondary || true
  fi
  if restore_bool nri_mention_resolver_timer_enabled "${nri_mention_resolver_timer_enabled:-false}"; then
    echo "Starting nri-mention-resolver.timer"
    sudo systemctl start nri-mention-resolver.timer || true
  fi
  if restore_bool nri_loop_timer_enabled "${nri_loop_timer_enabled:-false}"; then
    echo "Starting nri-loop.timer"
    sudo systemctl start nri-loop.timer || true
  fi
  rm -f "$STATE"
fi

echo "Resume complete. Consider: sudo systemctl restart news-intelligence-api-public"
